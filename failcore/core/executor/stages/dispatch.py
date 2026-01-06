# failcore/core/executor/stages/dispatch.py
"""
Dispatch Stage - tool execution with optional ProcessExecutor and SideEffectProbe
"""

from typing import Optional, Any, List

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult
from ...trace import ExecutionPhase


class DispatchStage:
    """Stage 6: Execute tool (with optional ProcessExecutor and SideEffectProbe)"""
    
    def __init__(self, process_executor: Optional[Any] = None):
        """
        Initialize dispatch stage
        
        Args:
            process_executor: Optional ProcessExecutor for isolated execution
        """
        self.process_executor = process_executor
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Execute tool function
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult if execution fails, None if successful
        
        Note:
            - Sets state.output (normalized)
            - Sets state.actual_usage (if extracted)
            - Can use ProcessExecutor for isolation
            - Can use SideEffectProbe for side-effect detection
        """
        # Get tool function
        fn = services.tools.get(state.step.tool)
        if fn is None:
            return services.failure_builder.fail(
                state=state,
                error_code="TOOL_NOT_FOUND",
                message=f"Tool not found: {state.step.tool}",
                phase=ExecutionPhase.EXECUTE,
            )
        
        try:
            # Optionally use ProcessExecutor for isolation
            if self.process_executor:
                result = self.process_executor.execute(fn, state.step.params, state.ctx.run_id)
                if not result.get("ok", False):
                    error = result.get("error", {})
                    return services.failure_builder.fail(
                        state=state,
                        error_code=error.get("code", "TOOL_EXECUTION_FAILED"),
                        message=error.get("message", "Tool execution failed"),
                        phase=ExecutionPhase.EXECUTE,
                    )
                out = result.get("result")
            else:
                # Direct execution
                out = fn(**state.step.params)
            
            # Normalize output
            output = services.output_normalizer.normalize(out)
            state.output = output
            
            # Extract actual usage from tool output (if available)
            if services.usage_extractor:
                actual_usage = services.usage_extractor.extract(
                    tool_output=out,
                    run_id=state.ctx.run_id,
                    step_id=state.step.id,
                    tool_name=state.step.tool,
                )
                if actual_usage:
                    state.actual_usage = actual_usage
            
            # Detect and record side-effects (post-execution observation)
            observed = self._detect_and_record_side_effects(state, services, out)
            state.observed_side_effects = observed
            
            # Mark taint tags for source tools (post-execution)
            if services.taint_engine and services.taint_store:
                self._mark_taint_tags(state, services, output)
            
            return None  # Continue to next stage
        
        except Exception as e:
            import traceback
            code = "TOOL_RAISED"
            msg = f"{type(e).__name__}: {e}"
            detail = {}
            if hasattr(services.failure_builder, 'summarizer') and services.failure_builder.summarizer:
                # Include stack if config allows
                detail["stack"] = traceback.format_exc()
            
            return services.failure_builder.fail(
                state=state,
                error_code=code,
                message=msg,
                phase=ExecutionPhase.EXECUTE,
                detail=detail,
            )
    
    def _detect_and_record_side_effects(
        self,
        state: ExecutionState,
        services: ExecutionServices,
        tool_output: Any,
    ) -> List[Any]:
        """
        Detect and record side-effects from tool execution
        
        Args:
            state: Execution state
            services: Execution services
            tool_output: Tool output (may contain side-effect hints)
        
        Returns:
            List of SideEffectEvent objects observed
        """
        from failcore.core.guards.effects.detection import (
            detect_filesystem_side_effect,
            detect_network_side_effect,
            detect_exec_side_effect,
        )
        from failcore.core.guards.effects.events import SideEffectEvent
        from ...trace.events import EventType, TraceEvent, LogLevel, utc_now_iso
        from failcore.core.guards.effects.side_effects import get_category_for_type
        
        # Detect side-effects from tool name and params
        side_effect_events = []
        side_effects = []
        
        # Filesystem side-effects
        fs_read = detect_filesystem_side_effect(state.step.tool, state.step.params, "read")
        if fs_read:
            side_effects.append((fs_read, state.step.params.get("path") or state.step.params.get("file")))
        
        fs_write = detect_filesystem_side_effect(state.step.tool, state.step.params, "write")
        if fs_write:
            side_effects.append((fs_write, state.step.params.get("path") or state.step.params.get("file")))
        
        fs_delete = detect_filesystem_side_effect(state.step.tool, state.step.params, "delete")
        if fs_delete:
            side_effects.append((fs_delete, state.step.params.get("path") or state.step.params.get("file")))
        
        # Network side-effects
        net_egress = detect_network_side_effect(state.step.tool, state.step.params, "egress")
        if net_egress:
            side_effects.append((net_egress, state.step.params.get("url") or state.step.params.get("host")))
        
        # Exec side-effects
        exec_effect = detect_exec_side_effect(state.step.tool, state.step.params)
        if exec_effect:
            side_effects.append((exec_effect, state.step.params.get("command") or state.step.params.get("cmd")))
        
        # Record each detected side-effect
        for side_effect_type, target in side_effects:
            if side_effect_type:
                # Create SideEffectEvent
                side_effect_event = SideEffectEvent(
                    type=side_effect_type,
                    target=target,
                    tool=state.step.tool,
                    step_id=state.step.id,
                )
                side_effect_events.append(side_effect_event)
                
                # Record to trace
                if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                    seq = services.recorder.next_seq()
                    category = get_category_for_type(side_effect_type).value
                    
                    event = TraceEvent(
                        schema="failcore.trace.v0.1.3",
                        seq=seq,
                        ts=utc_now_iso(),
                        level=LogLevel.INFO,
                        event={
                            "type": EventType.SIDE_EFFECT_APPLIED.value,
                            "severity": "ok",
                            "step": {
                                "id": state.step.id,
                                "tool": state.step.tool,
                                "attempt": state.attempt,
                            },
                            "data": {
                                "side_effect": {
                                    "type": side_effect_type.value,
                                    "target": target,
                                    "category": category,
                                    "tool": state.step.tool,
                                    "step_id": state.step.id,
                                    "metadata": {},
                                }
                            },
                        },
                        run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
                    )
                    
                    try:
                        services.recorder.record(event)
                    except Exception:
                        # Don't fail execution if side-effect recording fails
                        pass
        
        state.observed_side_effects = side_effect_events
        return side_effect_events
    
    def _mark_taint_tags(
        self,
        state: ExecutionState,
        services: ExecutionServices,
        output: Any,
    ) -> None:
        """
        Mark taint tags for source tools (post-execution)
        
        Uses summarized output to avoid performance issues with large objects.
        
        Args:
            state: Execution state
            services: Execution services
            output: Normalized StepOutput
        """
        if not services.taint_engine or not services.taint_store:
            return
        
        # Check if this is a source tool
        if not services.taint_store.is_source_tool(state.step.tool):
            return
        
        # Use summarized output (not full object) for taint marking
        # Get output value (may be large, but we only need it for pattern detection)
        output_value = output.value if hasattr(output, 'value') else output
        
        # Build context for on_call_success
        dlp_context = {
            "tool": state.step.tool,
            "params": state.step.params,
            "step_id": state.step.id,
            "run_id": state.ctx.run_id,
        }
        
        # Event emitter (optional, for audit)
        def emit_taint_event(event_data: Dict[str, Any]) -> None:
            """Emit taint event (for audit)"""
            pass  # Could record to trace if needed
        
        try:
            # Call DLP middleware on_call_success to mark taint tags
            services.taint_engine.on_call_success(
                tool_name=state.step.tool,
                params=state.step.params,
                context=dlp_context,
                result=output_value,  # Pass output for sensitivity inference
                emit=emit_taint_event,
            )
            
            # Store taint tags in state for trace/audit
            if services.taint_store.is_tainted(state.step.id):
                state.taint_tags = list(services.taint_store.get_tags(state.step.id))
        
        except Exception as e:
            # Don't fail execution if taint marking fails
            import logging
            logging.warning(
                f"Taint marking failed (non-fatal): {type(e).__name__}: {e}",
                exc_info=True,
            )