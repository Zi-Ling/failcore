"""
Cost Guardrails - Middleware

Budget enforcement in execution pipeline (circuit breaker)
"""

from typing import Dict, Any, Optional, Callable
from .models import Budget, CostUsage
from .estimator import CostEstimator
from .tracker import CostTracker


class BudgetGuardMiddleware:
    """
    Budget guard middleware for Executor/ToolRuntime
    
    Integration flow:
    1. on_call_start: Estimate cost, check if would exceed budget
    2. If exceeds: Circuit breaker - raise ECONOMIC_BUDGET_EXCEEDED
    3. on_call_success: Record actual cost usage
    4. Write to trace + receipt for audit trail
    """
    
    def __init__(
        self,
        budget: Budget,
        estimator: CostEstimator = None,
        tracker: CostTracker = None,
        warning_threshold: float = 0.8,  # Warn at 80% budget
    ):
        """
        Args:
            budget: Budget constraints
            estimator: Cost estimator
            tracker: Cost tracker
            warning_threshold: Emit warning at this usage percentage
        """
        self.budget = budget
        self.estimator = estimator or CostEstimator()
        self.tracker = tracker or CostTracker()
        self.warning_threshold = warning_threshold
    
    def on_call_start(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        emit: Optional[Callable] = None,
    ) -> Optional[CostUsage]:
        """
        Called before tool execution
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            context: Execution context (run_id, step_id, metadata)
            emit: Event emitter
        
        Returns:
            Estimated CostUsage
        
        Raises:
            FailCoreError if estimated cost would exceed budget
        """
        # Estimate cost
        metadata = context.get("metadata", {})
        estimated_usage = self.estimator.estimate(tool_name, params, metadata)
        
        # Fill in run_id/step_id
        estimated_usage.run_id = context.get("run_id", "")
        estimated_usage.step_id = context.get("step_id", "")
        
        # Check if would exceed budget
        would_exceed, reason, error_code = self.budget.would_exceed(estimated_usage)
        
        if would_exceed:
            # Circuit breaker: block execution
            from failcore.core.errors import FailCoreError, codes
            
            raise FailCoreError(
                message=f"Budget exceeded: {reason}",
                error_code=codes.ECONOMIC_BUDGET_EXCEEDED,
                phase="BUDGET_CHECK",
                suggestion=self._get_budget_exceeded_suggestion(),
                details={
                    "estimated_cost_usd": estimated_usage.cost_usd,
                    "estimated_tokens": estimated_usage.total_tokens,
                    "remaining_budget_usd": self.budget.remaining_cost_usd(),
                    "remaining_tokens": self.budget.remaining_tokens(),
                    "usage_percentage": self.budget.usage_percentage(),
                }
            )
        
        # Check if approaching limit (warning)
        if self.budget.usage_percentage() >= self.warning_threshold:
            if emit:
                emit({
                    "type": "BUDGET_WARNING",
                    "usage_percentage": self.budget.usage_percentage(),
                    "remaining_usd": self.budget.remaining_cost_usd(),
                    "remaining_tokens": self.budget.remaining_tokens(),
                })
        
        return estimated_usage
    
    def on_call_success(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        result: Any,
        emit: Optional[Callable] = None,
    ) -> None:
        """
        Called after successful tool execution
        
        Record actual cost usage
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            context: Execution context
            result: Tool result (may contain actual cost info)
            emit: Event emitter
        """
        # Try to extract actual cost from result
        actual_usage = self._extract_actual_cost(
            tool_name,
            params,
            context,
            result
        )
        
        # If no actual cost, use estimated
        if actual_usage is None:
            metadata = context.get("metadata", {})
            actual_usage = self.estimator.estimate(tool_name, params, metadata)
            actual_usage.run_id = context.get("run_id", "")
            actual_usage.step_id = context.get("step_id", "")
            actual_usage.estimated = True
        
        # Record usage
        self.tracker.record(actual_usage)
        
        # Update budget
        self.budget.add_usage(actual_usage)
        
        # Emit cost event
        if emit:
            emit({
                "type": "COST_RECORDED",
                "cost_usd": actual_usage.cost_usd,
                "tokens": actual_usage.total_tokens,
                "estimated": actual_usage.estimated,
                "budget_used": self.budget.usage_percentage(),
            })
    
    def on_call_error(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        error: Exception,
        emit: Optional[Callable] = None,
    ) -> None:
        """
        Called on tool execution error
        
        Still record estimated cost (partial execution may have occurred)
        """
        # Estimate cost for failed call
        metadata = context.get("metadata", {})
        estimated_usage = self.estimator.estimate(tool_name, params, metadata)
        estimated_usage.run_id = context.get("run_id", "")
        estimated_usage.step_id = context.get("step_id", "")
        estimated_usage.estimated = True
        
        # Record partial cost
        self.tracker.record(estimated_usage)
        self.budget.add_usage(estimated_usage)
    
    def _extract_actual_cost(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        result: Any,
    ) -> Optional[CostUsage]:
        """
        Extract actual cost from tool result
        
        Looks for cost info in result metadata
        """
        # Check if result has cost metadata
        if isinstance(result, dict):
            if "usage" in result or "cost" in result:
                usage_data = result.get("usage") or result.get("cost")
                
                if isinstance(usage_data, dict):
                    return CostUsage(
                        run_id=context.get("run_id", ""),
                        step_id=context.get("step_id", ""),
                        tool_name=tool_name,
                        input_tokens=usage_data.get("input_tokens", 0),
                        output_tokens=usage_data.get("output_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0),
                        cost_usd=usage_data.get("cost_usd", 0.0),
                        estimated=False,  # Actual cost
                        api_calls=1,
                        model=usage_data.get("model"),
                        provider=usage_data.get("provider"),
                    )
        
        return None
    
    def _get_budget_exceeded_suggestion(self) -> str:
        """Get suggestion for budget exceeded error"""
        suggestions = []
        
        if self.budget.remaining_tokens() is not None and self.budget.remaining_tokens() < 1000:
            suggestions.append("Reduce output length or use smaller model")
        
        if self.budget.remaining_cost_usd() is not None and self.budget.remaining_cost_usd() < 0.01:
            suggestions.append("Increase budget or shorten execution chain")
        
        suggestions.append("Use cheaper tools or enable caching")
        
        return "; ".join(suggestions)


__all__ = ["BudgetGuardMiddleware"]
