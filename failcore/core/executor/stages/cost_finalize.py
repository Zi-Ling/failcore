# failcore/core/executor/stages/cost_finalize.py
"""
Cost Finalize Stage - finalize cost metrics and record to storage
"""

from typing import Optional

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult
from ...cost.execution import build_cost_metrics


class CostFinalizeStage:
    """Stage 7: Finalize cost metrics and record to storage"""
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Finalize cost metrics and record to storage
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            None (always continues - this is final stage before success)
        
        Note:
            - Uses actual_usage if available, otherwise estimated_usage
            - commit=True for actual execution (adopts suggestion 6)
            - Sets state.cost_metrics
        """
        # Determine final usage (actual preferred, fallback to estimated)
        final_usage = state.actual_usage if state.actual_usage else state.estimated_usage
        
        if final_usage and services.cost_guardian:
            # Build cost metrics (commit=True for actual execution)
            cost_metrics = build_cost_metrics(
                run_id=state.ctx.run_id,
                usage=final_usage,
                accumulator=services.cost_accumulator,
                commit=True,  # Commit actual execution cost (adopts suggestion 6)
            )
            state.cost_metrics = cost_metrics
            
            # Update CostGuardian's budget counter
            try:
                services.cost_guardian.add_usage(final_usage)
            except Exception:
                # Don't fail execution if budget recording fails
                pass
        
        return None  # Continue (success path)
