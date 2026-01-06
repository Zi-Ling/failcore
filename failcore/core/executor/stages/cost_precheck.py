# failcore/core/executor/stages/cost_precheck.py
"""
Cost Precheck Stage - estimate cost and check budget before execution
"""

from typing import Optional

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult
from ...trace import ExecutionPhase
from ...cost.models import CostUsage


class CostPrecheckStage:
    """Stage 3: Estimate cost and check budget (before execution)"""
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Estimate cost and check budget
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult if budget exceeded, None otherwise
        
        Note:
            - Sets state.estimated_usage (but does NOT commit to accumulator)
            - commit=False for pre-check (adopts suggestion 6)
        """
        if not services.cost_guardian or not services.cost_estimator:
            return None  # Cost tracking disabled
        
        # Estimate cost for this step
        tool_metadata = state.step.meta or {}
        estimated_usage = services.cost_estimator.estimate(
            tool_name=state.step.tool,
            params=state.step.params,
            metadata=tool_metadata,
        )
        
        # Fill in run/step context
        estimated_usage = CostUsage(
            run_id=state.ctx.run_id,
            step_id=state.step.id,
            tool_name=state.step.tool,
            model=estimated_usage.model,
            provider=estimated_usage.provider,
            input_tokens=estimated_usage.input_tokens,
            output_tokens=estimated_usage.output_tokens,
            total_tokens=estimated_usage.total_tokens,
            cost_usd=estimated_usage.cost_usd,
            estimated=True,
            api_calls=estimated_usage.api_calls,
        )
        
        state.estimated_usage = estimated_usage
        
        # Check budget (CRITICAL: this can block execution)
        allowed_by_budget, budget_reason, budget_error_code = services.cost_guardian.check_operation(
            estimated_usage,
            raise_on_exceed=False,
        )
        
        if not allowed_by_budget:
            # Build cost metrics for blocked step (commit=False)
            from ...cost.execution import build_cost_metrics
            cost_metrics = build_cost_metrics(
                run_id=state.ctx.run_id,
                usage=estimated_usage,
                accumulator=services.cost_accumulator,
                commit=False,  # Don't commit estimated cost (adopts suggestion 6)
            )
            
            # Map to canonical error codes
            from ...errors import codes
            if budget_error_code == "BURN_RATE_EXCEEDED":
                canonical_code = codes.ECONOMIC_BURN_RATE_EXCEEDED
            elif budget_error_code == "BUDGET_COST_EXCEEDED":
                canonical_code = codes.ECONOMIC_BUDGET_EXCEEDED
            elif budget_error_code == "BUDGET_TOKENS_EXCEEDED":
                canonical_code = codes.ECONOMIC_TOKEN_LIMIT
            else:
                canonical_code = codes.ECONOMIC_BUDGET_EXCEEDED
            
            return services.failure_builder.fail(
                state=state,
                error_code=canonical_code,
                message=budget_reason or "Budget or burn rate exceeded",
                phase=ExecutionPhase.POLICY,  # Budget check is policy-level protection
                details={
                    "budget_reason": budget_reason,
                    "budget_error_code": budget_error_code,
                    "estimated_cost_usd": estimated_usage.cost_usd,
                    "estimated_tokens": estimated_usage.total_tokens,
                },
                suggestion="Increase budget or wait before retrying" if budget_error_code == "BURN_RATE_EXCEEDED" else "Increase budget or optimize tool usage",
                metrics=cost_metrics,
            )
        
        return None  # Continue to next stage
