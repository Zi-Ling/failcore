# failcore/core/executor/validation.py
"""
Step Validation - parameter and precondition validation

This module handles validation of steps before execution:
- Basic parameter validation (structure, types)
- Precondition validation (using ValidationEngine)
"""

from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

from failcore.core.types.step import Step
from failcore.core.types.step import RunContext
from ..validate.contracts import Context as ValidationContext


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
    
    Uses ValidationEngine exclusively. This is the SINGLE validation point.
    """
    
    def __init__(
        self,
        validation_engine: Optional[Any] = None,  # ValidationEngine
    ):
        """
        Initialize validator
        
        Args:
            validation_engine: Optional ValidationEngine (if None, validation is skipped)
        """
        self.validation_engine = validation_engine
    
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
        Validate step preconditions using ValidationEngine.
        
        This is the SINGLE validation point in the execution pipeline.
        No other middleware or stage should perform validation.
        
        Args:
            step: Step to validate
            ctx: Run context
        
        Returns:
            ValidationFailure if validation fails, None otherwise
        """
        # Skip validation if no engine (policy=None case)
        if not self.validation_engine:
            return None
        
        # Create ValidationContext from Step and RunContext
        validation_ctx = ValidationContext(
            tool=step.tool,
            params=step.params,
            run_id=ctx.run_id,
            step_id=step.id,
        )
        
        # Evaluate using ValidationEngine
        decisions = self.validation_engine.evaluate(validation_ctx)
        
        # Check for blocking decisions
        for decision in decisions:
            if decision.is_blocking:
                # Extract details from evidence
                evidence = decision.evidence or {}
                suggestion = evidence.get("suggestion")
                remediation = evidence.get("remediation")
                
                return ValidationFailure(
                    code=decision.code,
                    message=decision.message,
                    details=evidence,
                    suggestion=suggestion,
                    remediation=remediation,
                )
        
        return None


__all__ = [
    "ValidationFailure",
    "StepValidator",
]
