# failcore/core/validate/builtin/type.py
"""
Type validation builtin for input parameters

Lightweight type gate focusing on:
1. Basic type matching (isinstance)
2. Required fields
3. Container type checking (first-level only)
4. Basic boundaries (max_length/max_items)

For complex validation (email/url/nested schemas), use Pydantic models.
"""

from typing import Any, Dict, List, Optional, Union, Type
from .contract import PreconditionValidator, ValidationResult


def type_check_precondition(
    param_name: str,
    expected_type: Union[Type, tuple],
    required: bool = True
) -> PreconditionValidator:
    """
    Type checking precondition
    
    Args:
        param_name: Parameter name to check
        expected_type: Expected type(s) - single type or tuple of types
        required: Whether parameter is required
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> registry.register_precondition(
        ...     "divide",
        ...     type_check_precondition("denominator", int, required=True)
        ... )
    """
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        if param_name not in params:
            if required:
                return ValidationResult.failure(
                    message=f"Required parameter '{param_name}' is missing",
                    code="PARAM_REQUIRED",
                    details={"param": param_name}
                )
            else:
                return ValidationResult.success(
                    message=f"Optional parameter '{param_name}' not provided"
                )
        
        value = params[param_name]
        
        # Check type
        if not isinstance(value, expected_type):
            expected_names = (
                expected_type.__name__ 
                if isinstance(expected_type, type) 
                else " or ".join(t.__name__ for t in expected_type)
            )
            return ValidationResult.failure(
                message=f"Parameter '{param_name}' must be {expected_names}, got {type(value).__name__}",
                code="PARAM_TYPE_MISMATCH",
                details={
                    "param": param_name,
                    "expected": expected_names,
                    "got": type(value).__name__
                }
            )
        
        return ValidationResult.success(
            message=f"Parameter '{param_name}' type check passed"
        )
    
    return PreconditionValidator(
        name=f"type_check({param_name})",
        condition=check,
        message=f"Type validation for '{param_name}'",
        code="PARAM_TYPE_MISMATCH"
    )


def required_fields_precondition(
    *field_names: str
) -> PreconditionValidator:
    """
    Required fields checker
    
    Args:
        *field_names: Names of required fields
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> registry.register_precondition(
        ...     "write_file",
        ...     required_fields_precondition("path", "content")
        ... )
    """
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        missing = [field for field in field_names if field not in params]
        
        if missing:
            return ValidationResult.failure(
                message=f"Missing required fields: {', '.join(missing)}",
                code="PARAM_REQUIRED",
                details={"missing_fields": missing}
            )
        
        return ValidationResult.success(
            message="All required fields present"
        )
    
    return PreconditionValidator(
        name=f"required_fields({','.join(field_names)})",
        condition=check,
        message="Required fields validation",
        code="PARAM_REQUIRED"
    )


def max_length_precondition(
    param_name: str,
    max_length: int
) -> PreconditionValidator:
    """
    Maximum length/size checker
    
    Works with: str, list, dict, bytes
    
    Args:
        param_name: Parameter name to check
        max_length: Maximum allowed length
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> # Prevent huge payloads
        >>> registry.register_precondition(
        ...     "write_file",
        ...     max_length_precondition("content", max_length=1000000)
        ... )
    """
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        if param_name not in params:
            return ValidationResult.success(
                message=f"Parameter '{param_name}' not provided, skipping length check"
            )
        
        value = params[param_name]
        
        # Check if value has length
        if not hasattr(value, '__len__'):
            return ValidationResult.success(
                message=f"Parameter '{param_name}' has no length attribute, skipping"
            )
        
        actual_length = len(value)
        
        if actual_length > max_length:
            return ValidationResult.failure(
                message=f"Parameter '{param_name}' exceeds max length: {actual_length} > {max_length}",
                code="PARAM_TOO_LARGE",
                details={
                    "param": param_name,
                    "max_length": max_length,
                    "actual_length": actual_length
                }
            )
        
        return ValidationResult.success(
            message=f"Parameter '{param_name}' length check passed"
        )
    
    return PreconditionValidator(
        name=f"max_length({param_name},{max_length})",
        condition=check,
        message="Length validation",
        code="PARAM_TOO_LARGE"
    )


def pydantic_adapter_precondition(
    model_class: Any,
    param_source: str = "params"
) -> PreconditionValidator:
    """
    Pydantic model validation adapter
    
    Captures Pydantic ValidationError and converts to structured result.
    
    Args:
        model_class: Pydantic model class
        param_source: Where to get params from context (default: "params")
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> from pydantic import BaseModel
        >>> class UserInput(BaseModel):
        ...     email: str
        ...     age: int
        >>> 
        >>> registry.register_precondition(
        ...     "create_user",
        ...     pydantic_adapter_precondition(UserInput)
        ... )
    """
    def check(ctx) -> ValidationResult:
        params = ctx.get(param_source, {})
        
        try:
            # Try to validate with Pydantic model
            model_class(**params)
            return ValidationResult.success(
                message=f"Pydantic validation passed for {model_class.__name__}"
            )
        except Exception as e:
            # Check if it's a Pydantic ValidationError
            error_type = type(e).__name__
            
            if error_type == "ValidationError" and hasattr(e, 'errors'):
                # Extract structured errors from Pydantic
                errors = []
                for err in e.errors():
                    errors.append({
                        "field": ".".join(str(x) for x in err.get("loc", [])),
                        "type": err.get("type", "unknown"),
                        "message": err.get("msg", str(e))
                    })
                
                return ValidationResult.failure(
                    message=f"Schema validation failed: {len(errors)} error(s)",
                    code="PARAM_SCHEMA_INVALID",
                    details={
                        "model": model_class.__name__,
                        "errors": errors
                    }
                )
            else:
                # Other exceptions
                return ValidationResult.failure(
                    message=f"Validation error: {str(e)}",
                    code="PARAM_INVALID",
                    details={"error": str(e)}
                )
    
    return PreconditionValidator(
        name=f"pydantic({model_class.__name__})",
        condition=check,
        message="Pydantic model validation",
        code="PARAM_SCHEMA_INVALID"
    )


__all__ = [
    "type_check_precondition",
    "required_fields_precondition",
    "max_length_precondition",
    "pydantic_adapter_precondition",
]

