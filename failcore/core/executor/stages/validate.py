# failcore/core/executor/stages/validate.py
"""
Validate Stage - parameter and precondition validation
"""

from typing import Optional

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult
from ...trace import ExecutionPhase


class ValidateStage:
    """Stage 2: Validate step parameters and preconditions"""
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Validate step parameters and preconditions
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult if validation fails, None otherwise
        """
        # Basic parameter validation
        ok, err = services.step_validator.validate_basic(state.step)
        if not ok:
            return services.failure_builder.fail(
                state=state,
                error_code="PARAM_INVALID",
                message=err,
                phase=ExecutionPhase.VALIDATE,
            )
        
        # Precondition validation
        validation_failure = services.step_validator.validate_preconditions(state.step, state.ctx)
        if validation_failure:
            return services.failure_builder.fail(
                state=state,
                error_code=validation_failure.code,
                message=validation_failure.message,
                phase=ExecutionPhase.VALIDATE,
                detail=validation_failure.details,
                suggestion=validation_failure.suggestion,
                remediation=validation_failure.remediation,
            )
        
        return None  # Continue to next stage
