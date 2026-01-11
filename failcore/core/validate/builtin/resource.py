# failcore/core/validate/builtin/resource.py
"""
Resource quota builtin

Prevent resource exhaustion attacks:
1. File size limits
2. Payload size limits
3. Collection size limits (prevent explosion)
"""

from typing import Any, Optional
import os

from .contract import PreconditionValidator, ValidationResult


def max_file_size_precondition(
    path_param: str = "path",
    max_bytes: int = 10 * 1024 * 1024  # 10MB default
) -> PreconditionValidator:
    """
    File size limit validator
    
    Checks file size before reading/processing to prevent memory exhaustion.
    
    Args:
        path_param: Parameter name containing file path
        max_bytes: Maximum allowed file size in bytes
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> # Limit file reads to 10MB
        >>> registry.register_precondition(
        ...     "read_file",
        ...     max_file_size_precondition("path", max_bytes=10*1024*1024)
        ... )
    """
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        if path_param not in params:
            return ValidationResult.success(
                message=f"Parameter '{path_param}' not provided"
            )
        
        file_path = params[path_param]
        
        if not isinstance(file_path, str):
            return ValidationResult.failure(
                message=f"Path parameter '{path_param}' must be a string",
                code="PARAM_TYPE_MISMATCH",
                details={"param": path_param, "got": type(file_path).__name__}
            )
        
        # Check if file exists
        if not os.path.exists(file_path):
            # Don't fail here - let the tool handle non-existent files
            return ValidationResult.success(
                message=f"File '{file_path}' does not exist, skipping size check"
            )
        
        # Check if it's a file (not directory)
        if not os.path.isfile(file_path):
            return ValidationResult.success(
                message=f"Path '{file_path}' is not a file, skipping size check"
            )
        
        try:
            file_size = os.path.getsize(file_path)
            
            if file_size > max_bytes:
                return ValidationResult.failure(
                    message=f"File size {file_size} bytes exceeds limit {max_bytes} bytes",
                    code="FILE_TOO_LARGE",
                    details={
                        "path": file_path,
                        "size_bytes": file_size,
                        "max_bytes": max_bytes,
                        "size_mb": round(file_size / 1024 / 1024, 2),
                        "max_mb": round(max_bytes / 1024 / 1024, 2)
                    }
                )
            
            return ValidationResult.success(
                message=f"File size check passed: {file_size} bytes"
            )
            
        except Exception as e:
            return ValidationResult.failure(
                message=f"File size check error: {str(e)}",
                code="PARAM_INVALID",
                details={"path": file_path, "error": str(e)}
            )
    
    return PreconditionValidator(
        name=f"max_file_size({path_param},{max_bytes})",
        condition=check,
        message="File size validation",
        code="FILE_TOO_LARGE"
    )


def max_payload_size_precondition(
    param_name: str,
    max_bytes: int = 1 * 1024 * 1024  # 1MB default
) -> PreconditionValidator:
    """
    Payload size limit validator
    
    Prevents huge payloads (especially for write operations, API requests).
    
    Args:
        param_name: Parameter name to check (typically "content", "data", "body")
        max_bytes: Maximum allowed size in bytes
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> # Limit write content to 1MB
        >>> registry.register_precondition(
        ...     "write_file",
        ...     max_payload_size_precondition("content", max_bytes=1024*1024)
        ... )
    """
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        if param_name not in params:
            return ValidationResult.success(
                message=f"Parameter '{param_name}' not provided"
            )
        
        payload = params[param_name]
        
        # Calculate size based on type
        try:
            if isinstance(payload, str):
                size_bytes = len(payload.encode('utf-8'))
            elif isinstance(payload, bytes):
                size_bytes = len(payload)
            elif isinstance(payload, (list, dict)):
                # Rough estimation using string representation
                size_bytes = len(str(payload).encode('utf-8'))
            else:
                # Unknown type, try to get length
                if hasattr(payload, '__len__'):
                    size_bytes = len(payload)
                else:
                    return ValidationResult.success(
                        message=f"Cannot determine size of '{param_name}', skipping"
                    )
            
            if size_bytes > max_bytes:
                return ValidationResult.failure(
                    message=f"Payload size {size_bytes} bytes exceeds limit {max_bytes} bytes",
                    code="PAYLOAD_TOO_LARGE",
                    details={
                        "param": param_name,
                        "size_bytes": size_bytes,
                        "max_bytes": max_bytes,
                        "size_kb": round(size_bytes / 1024, 2),
                        "max_kb": round(max_bytes / 1024, 2)
                    }
                )
            
            return ValidationResult.success(
                message=f"Payload size check passed: {size_bytes} bytes"
            )
            
        except Exception as e:
            return ValidationResult.failure(
                message=f"Payload size check error: {str(e)}",
                code="PARAM_INVALID",
                details={"param": param_name, "error": str(e)}
            )
    
    return PreconditionValidator(
        name=f"max_payload_size({param_name},{max_bytes})",
        condition=check,
        message="Payload size validation",
        code="PAYLOAD_TOO_LARGE"
    )


def max_collection_size_precondition(
    param_name: str,
    max_items: int = 1000
) -> PreconditionValidator:
    """
    Collection size limit validator
    
    Prevents collection explosion (e.g., huge arrays, deeply nested structures).
    
    Args:
        param_name: Parameter name containing collection (list, dict, set, etc.)
        max_items: Maximum allowed number of items
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> # Limit batch operations to 1000 items
        >>> registry.register_precondition(
        ...     "batch_process",
        ...     max_collection_size_precondition("items", max_items=1000)
        ... )
    """
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        if param_name not in params:
            return ValidationResult.success(
                message=f"Parameter '{param_name}' not provided"
            )
        
        collection = params[param_name]
        
        # Check if it's a collection
        if not hasattr(collection, '__len__'):
            return ValidationResult.success(
                message=f"Parameter '{param_name}' is not a collection, skipping"
            )
        
        try:
            count = len(collection)
            
            if count > max_items:
                return ValidationResult.failure(
                    message=f"Collection size {count} exceeds limit {max_items}",
                    code="COLLECTION_TOO_LARGE",
                    details={
                        "param": param_name,
                        "count": count,
                        "max_items": max_items
                    }
                )
            
            return ValidationResult.success(
                message=f"Collection size check passed: {count} items"
            )
            
        except Exception as e:
            return ValidationResult.failure(
                message=f"Collection size check error: {str(e)}",
                code="PARAM_INVALID",
                details={"param": param_name, "error": str(e)}
            )
    
    return PreconditionValidator(
        name=f"max_collection_size({param_name},{max_items})",
        condition=check,
        message="Collection size validation",
        code="COLLECTION_TOO_LARGE"
    )


__all__ = [
    "max_file_size_precondition",
    "max_payload_size_precondition",
    "max_collection_size_precondition",
]

