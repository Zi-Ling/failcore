# failcore/core/executor/stages/cost_finalize.py
"""
Cost Finalize Stage - finalize cost metrics and record to storage
"""

from typing import Optional, Any

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
        # Determine final usage with conflict resolution
        # Priority: provider_reported > gateway_reported > step.meta > estimated > streaming
        # Special handling: If streaming usage exists, correct it with provider usage if available
        final_usage = self._resolve_usage_conflict(
            state,
            services,
        )
        
        # Streaming correction: If we have streaming usage but provider usage is available, use provider
        if final_usage and final_usage.source == "streaming" and state.actual_usage:
            if state.actual_usage.source in ("provider_reported", "gateway_reported"):
                # Correct streaming estimate with actual provider usage
                final_usage = state.actual_usage
        
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
    
    def _resolve_usage_conflict(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[Any]:  # Optional[CostUsage]
        """
        Resolve usage conflict between multiple sources
        
        Priority: provider_reported > gateway_reported > step.meta > estimated
        
        If conflict detected (>30% difference), use more conservative value (max)
        and record COST_USAGE_CONFLICT event.
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            Resolved CostUsage (or None if no usage)
        """
        from ...cost.models import CostUsage
        
        # Collect all usage candidates
        candidates = []
        
        # 1. Actual usage (from extractor) - highest priority
        if state.actual_usage:
            candidates.append(("actual", state.actual_usage))
        
        # 2. Step metadata (user-provided)
        if state.step.meta:
            meta_cost = state.step.meta.get("cost_usd")
            if meta_cost is not None:
                try:
                    meta_cost = float(meta_cost) if isinstance(meta_cost, (int, float, str)) else None
                    if meta_cost is not None and meta_cost > 0:
                        # Create usage from meta
                        base_usage = state.actual_usage or state.estimated_usage
                        if base_usage:
                            meta_usage = CostUsage(
                                run_id=base_usage.run_id,
                                step_id=base_usage.step_id,
                                tool_name=base_usage.tool_name,
                                model=base_usage.model,
                                provider=base_usage.provider,
                                input_tokens=base_usage.input_tokens,
                                output_tokens=base_usage.output_tokens,
                                total_tokens=base_usage.total_tokens,
                                cost_usd=meta_cost,
                                estimated=True,
                                source="step_meta",
                                api_calls=base_usage.api_calls,
                            )
                            candidates.append(("step_meta", meta_usage))
                except (ValueError, TypeError):
                    pass
        
        # 3. Estimated usage (from estimator)
        if state.estimated_usage:
            candidates.append(("estimated", state.estimated_usage))
        
        if not candidates:
            return None
        
        # Sort by priority
        priority_order = {
            "provider_reported": 1,
            "gateway_reported": 2,
            "step_meta": 3,
            "estimated": 4,
            "streaming": 5,
            "unknown": 6,
        }
        
        # Sort candidates by source priority
        candidates.sort(key=lambda x: priority_order.get(x[1].source, 99))
        
        # Use highest priority candidate
        final_usage = candidates[0][1]
        
        # Check for conflicts (if multiple candidates with different costs)
        if len(candidates) > 1:
            costs = [c[1].cost_usd for c in candidates if c[1].cost_usd > 0]
            if len(costs) > 1:
                max_cost = max(costs)
                min_cost = min(costs)
                if max_cost > 0:
                    from ...config.cost import COST_CONFLICT_THRESHOLD
                    diff_ratio = (max_cost - min_cost) / max_cost
                    if diff_ratio > COST_CONFLICT_THRESHOLD:
                        # Conflict detected - use more conservative (max) value
                        # and record conflict event
                        self._record_cost_conflict(services, state, candidates, final_usage)
                        
                        # Use max cost (more conservative for budget protection)
                        if final_usage.cost_usd < max_cost:
                            from ...cost.models import CostUsage
                            final_usage = CostUsage(
                                run_id=final_usage.run_id,
                                step_id=final_usage.step_id,
                                tool_name=final_usage.tool_name,
                                model=final_usage.model,
                                provider=final_usage.provider,
                                input_tokens=final_usage.input_tokens,
                                output_tokens=final_usage.output_tokens,
                                total_tokens=final_usage.total_tokens,
                                cost_usd=max_cost,  # Use max (conservative)
                                estimated=final_usage.estimated,
                                source=final_usage.source,
                                api_calls=final_usage.api_calls,
                            )
                        
                        # Use max cost (more conservative for budget protection)
                        if final_usage.cost_usd < max_cost:
                            final_usage = CostUsage(
                                run_id=final_usage.run_id,
                                step_id=final_usage.step_id,
                                tool_name=final_usage.tool_name,
                                model=final_usage.model,
                                provider=final_usage.provider,
                                input_tokens=final_usage.input_tokens,
                                output_tokens=final_usage.output_tokens,
                                total_tokens=final_usage.total_tokens,
                                cost_usd=max_cost,  # Use max (conservative)
                                estimated=final_usage.estimated,
                                source=final_usage.source,
                                api_calls=final_usage.api_calls,
                            )
        
        return final_usage
    
    def _record_cost_conflict(
        self,
        services: ExecutionServices,
        state: ExecutionState,
        candidates: list,
        final_usage: Any,
    ) -> None:
        """Record cost usage conflict event"""
        from ...trace.events import TraceEvent, EventType, LogLevel, utc_now_iso
        
        if not hasattr(services.recorder, 'next_seq') or state.seq is None:
            return
        
        seq = services.recorder.next_seq()
        
        # Build conflict details
        conflict_details = []
        for source_name, usage in candidates:
            conflict_details.append({
                "source": source_name,
                "usage_source": usage.source,
                "cost_usd": usage.cost_usd,
                "tokens": usage.total_tokens,
            })
        
        event = TraceEvent(
            schema="failcore.trace.v0.1.3",
            seq=seq,
            ts=utc_now_iso(),
            level=LogLevel.WARN,  # Warning level
            event={
                "type": EventType.STEP_END.value,  # Use STEP_END for cost conflict warnings
                "severity": "warn",
                "step": {
                    "id": state.step.id,
                    "tool": state.step.tool,
                    "attempt": state.attempt,
                },
                "data": {
                    "message": "Cost usage conflict detected (>30% difference between sources)",
                    "category": "cost_usage_conflict",
                    "tool": state.step.tool,
                    "conflict_details": conflict_details,
                    "resolved_cost_usd": final_usage.cost_usd,
                    "resolved_source": final_usage.source,
                },
            },
            run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
        )
        
        try:
            services.recorder.record(event)
        except Exception:
            # Don't fail execution if event recording fails
            pass