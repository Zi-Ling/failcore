# failcore/core/validate/validators/security.py
"""
Security-focused validators for path traversal, sandbox enforcement, etc.

This module provides validators for production security requirements:
- Path traversal detection (../ attacks)
- Sandbox boundary enforcement
- Symlink resolution checks
"""

from pathlib import Path
import os
from typing import Any, Dict
from ..validator import (
    PreconditionValidator,
    ValidationResult,
)


def path_traversal_precondition(
    *param_names: str,
    sandbox_root: str = None
) -> PreconditionValidator:
    """
    Path traversal defense validator
    
    Checks if path attempts to escape sandbox:
    - Resolves .. and symlinks
    - Normalizes path
    - Validates path is within sandbox_root
    
    Args:
        *param_names: Parameter names to check (path, file_path, etc.)
        sandbox_root: Sandbox root directory (uses cwd if None)
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> from failcore.core.validate.validators.security import path_traversal_precondition
        >>> registry.register_precondition(
        ...     "write_file",
        ...     path_traversal_precondition("path", sandbox_root="/app/workspace")
        ... )
    """
    if not param_names:
        param_names = ("path",)
    
    # Determine sandbox root directory
    if sandbox_root is None:
        sandbox_root = os.getcwd()
    
    sandbox_root = Path(sandbox_root).resolve()
    
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        # Find first existing parameter
        path_value = None
        found_param = None
        for pname in param_names:
            if pname in params:
                path_value = params[pname]
                found_param = pname
                break
        
        if not path_value:
            # No path parameter found, skip check
            return ValidationResult.success(
                message="No path parameter found",
                code="PATH_CHECK_SKIPPED"
            )
        
        try:
            # Normalize path (resolve handles .. and symlinks)
            target_path = Path(path_value)
            
            # If relative path, resolve based on sandbox root
            if not target_path.is_absolute():
                target_path = sandbox_root / target_path
            
            # Resolve to absolute path
            resolved_path = target_path.resolve()
            
            # Check if within sandbox
            try:
                resolved_path.relative_to(sandbox_root)
            except ValueError:
                # relative_to raises ValueError if not within subdirectory
                # Distinguish between path traversal (../) and absolute path outside sandbox
                is_traversal_attempt = ".." in str(path_value) or path_value.startswith(("../", "..\\"))
                
                if is_traversal_attempt:
                    return ValidationResult.failure(
                        message=f"Path traversal detected: '{path_value}' attempts to escape sandbox using '../'",
                        code="PATH_TRAVERSAL",
                        details={
                            "path": str(path_value),
                            "sandbox": str(sandbox_root),
                            "resolved": str(resolved_path),
                            "suggestion": "Remove '../' path components"
                        }
                    )
                else:
                    return ValidationResult.failure(
                        message=f"Path is outside sandbox boundary: '{path_value}'",
                        code="SANDBOX_VIOLATION",
                        details={
                            "path": str(path_value),
                            "sandbox": str(sandbox_root),
                            "resolved": str(resolved_path),
                            "suggestion": f"Path must be within sandbox: {sandbox_root}"
                        }
                    )
            
            # Path is within sandbox, pass check
            return ValidationResult.success(
                message=f"Path '{path_value}' is within sandbox",
                code="PATH_SAFE"
            )
            
        except Exception as e:
            # Path resolution failed (e.g., invalid path format)
            return ValidationResult.failure(
                message=f"Invalid path: {e}",
                code="PATH_INVALID",
                details={"suggestion": "Provide a valid file path"}
            )
    
    return PreconditionValidator(
        name=f"path_traversal_check({'|'.join(param_names)})",
        condition=check,
        message="Path traversal detected",
        code="PATH_TRAVERSAL"
    )


__all__ = [
    "path_traversal_precondition",
]

