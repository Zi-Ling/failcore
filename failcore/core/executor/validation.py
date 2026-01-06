# failcore/core/executor/validation.py
"""
Step Validation - parameter and precondition validation

This module handles validation of steps before execution:
- Basic parameter validation (structure, types)
- Precondition validation (using ValidatorRegistry)
"""

from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

from failcore.core.types.step import Step
from ..validate import ValidatorRegistry
from failcore.core.types.step import RunContext


@dataclass
class ValidationFailure:
    """Validation failure information"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestion: Optional[str] = None
    remediation: Optional[Dict[str, Any]] = None


class StepValidator:
    """
    Step validation logic
    
    Handles both basic parameter validation and precondition validation.
    """
    
    def __init__(self, validator_registry: Optional[ValidatorRegistry] = None):
        """
        Initialize validator
        
        Args:
            validator_registry: Optional ValidatorRegistry for precondition checks
        """
        self.validator = validator_registry
    
    def validate_basic(self, step: Step) -> Tuple[bool, str]:
        """
        Validate basic step structure
        
        Args:
            step: Step to validate
        
        Returns:
            (is_valid, error_message)
        """
        if not step.id.strip():
            return False, "step.id is empty"
        
        if not step.tool.strip():
            return False, "step.tool is empty"
        
        if not isinstance(step.params, dict):
            return False, "step.params must be a dict"
        
        # Validate param keys
        for k in step.params.keys():
            if not isinstance(k, str) or not k.strip():
                return False, f"invalid param key: {k!r}"
        
        return True, ""
    
    def validate_preconditions(
        self,
        step: Step,
        ctx: RunContext,
    ) -> Optional[ValidationFailure]:
        """
        Validate step preconditions
        
        Args:
            step: Step to validate
            ctx: Run context
        
        Returns:
            ValidationFailure if validation fails, None otherwise
        """
        if not self.validator or not self.validator.has_preconditions(step.tool):
            return None
        
        validation_context = {
            "step": step,
            "params": step.params,
            "ctx": ctx,
        }
        
        validation_results = self.validator.validate_preconditions(step.tool, validation_context)
        
        for result in validation_results:
            if not result.valid:
                # Extract suggestion/remediation from ValidationResult.details
                details = result.details or {}
                suggestion = details.get("suggestion")
                remediation = details.get("remediation")
                
                return ValidationFailure(
                    code=result.code or "PRECONDITION_FAILED",
                    message=result.message,
                    details=details,
                    suggestion=suggestion,
                    remediation=remediation,
                )
        
        return None


__all__ = [
    "ValidationFailure",
    "StepValidator",
]
