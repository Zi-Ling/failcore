# failcore/core/executor/failure.py
"""
Failure Builder - unified failure handling (adopts suggestion 4)

This module provides a unified failure handler that can be called from any stage.
It ensures consistent failure handling and trace recording.

Design principle:
- Any stage can call failure_builder.fail() to handle failures
- Avoids "failure logic only at end of pipeline" edge cases
"""

from typing import Dict, Any, Optional
import time

from failcore.core.types.step import StepResult, StepStatus, StepError
from ..trace import build_result_event, ExecutionPhase
from ..trace.events import TraceStepStatus
from ..trace.summarize import OutputSummarizer, SummarizeConfig
from .state import ExecutionState, ExecutionServices


class FailureBuilder:
    """
    Unified failure handler
    
    Can be called from any stage to handle failures consistently.
    Records STEP_END event and cost storage (if applicable).
    """
    
    def __init__(self, services: ExecutionServices, summarize_config: Optional[SummarizeConfig] = None):
        """
        Initialize failure builder
        
        Args:
            services: ExecutionServices instance
            summarize_config: Optional summarization config
        """
        self.services = services
        self.summarizer = OutputSummarizer(summarize_config) if summarize_config else None
    
    def fail(
        self,
        state: ExecutionState,
        error_code: str,
        message: str,
        phase: ExecutionPhase,
        detail: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        remediation: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> StepResult:
        """
        Build failure StepResult and record trace/cost
        
        Args:
            state: Execution state
            error_code: Error code
            message: Error message
            phase: Execution phase where failure occurred
            detail: Optional error detail dict
            suggestion: Optional LLM-friendly suggestion
            remediation: Optional remediation dict
            details: Optional details dict (merged with detail)
            metrics: Optional cost metrics
        
        Returns:
            StepResult with failure status
        
        Note:
            - Records STEP_END event
            - Records cost storage (if metrics provided, commit=False for blocked steps)
            - Determines status based on phase (BLOCKED for VALIDATE/POLICY, FAIL otherwise)
        """
        finished_at, duration_ms = self._finish_times(state.t0)
        
        # Merge LLM-friendly fields into detail
        merged_detail = detail or details or {}
        if suggestion:
            merged_detail["suggestion"] = suggestion
        if remediation:
            merged_detail["remediation"] = remediation
        
        # Determine status based on phase (v0.1.2 semantic)
        if phase in (ExecutionPhase.VALIDATE, ExecutionPhase.POLICY):
            trace_status = TraceStepStatus.BLOCKED
            result_status = StepStatus.BLOCKED
        else:
            trace_status = TraceStepStatus.FAIL
            result_status = StepStatus.FAIL
        
        # Truncate message if summarizer available
        truncated_message = message
        if self.summarizer:
            truncated_message = self.summarizer.truncate(message)
        
        # Record STEP_END
        if hasattr(self.services.recorder, 'next_seq'):
            seq = self.services.recorder.next_seq()
            state.seq = seq
            
            self._record(
                build_result_event(
                    seq=seq,
                    run_context=state.run_ctx,
                    step_id=state.step.id,
                    tool=state.step.tool,
                    attempt=state.attempt,
                    status=trace_status,
                    phase=phase,
                    duration_ms=duration_ms,
                    error={
                        "code": error_code,
                        "message": truncated_message,
                        "detail": merged_detail,
                    },
                    metrics=metrics,
                )
            )
            
            # Record to cost storage (even for failed/blocked steps)
            # commit=False for blocked steps (adopts suggestion 6)
            if self.services.cost_recorder and metrics and "cost" in metrics:
                commit = phase not in (ExecutionPhase.VALIDATE, ExecutionPhase.POLICY)
                self.services.cost_recorder.record_step(
                    run_id=state.ctx.run_id,
                    step_id=state.step.id,
                    seq=seq,
                    tool=state.step.tool,
                    usage=None,  # Will use metrics
                    metrics=metrics,
                    status=trace_status.value if isinstance(trace_status, TraceStepStatus) else str(trace_status),
                    started_at=state.started_at,
                    duration_ms=duration_ms,
                    error_code=error_code,
                    commit=commit,
                )
                
                # Update run summary
                cumulative = metrics["cost"]["cumulative"]
                self.services.cost_recorder.record_run_summary(
                    run_id=state.ctx.run_id,
                    created_at=state.ctx.created_at,
                    cumulative=cumulative,
                    seq=seq,
                    status="blocked" if trace_status == TraceStepStatus.BLOCKED else "error",
                    blocked_step_id=state.step.id if trace_status == TraceStepStatus.BLOCKED else None,
                    blocked_reason=truncated_message if trace_status == TraceStepStatus.BLOCKED else None,
                    blocked_error_code=error_code if trace_status == TraceStepStatus.BLOCKED else None,
                )
        
        return StepResult(
            step_id=state.step.id,
            tool=state.step.tool,
            status=result_status,
            started_at=state.started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            output=None,
            error=StepError(
                error_code=error_code,
                message=truncated_message,
                detail=merged_detail,
            ),
            meta={"phase": phase.value},
        )
    
    def _record(self, event: Any) -> None:
        """Record trace event (fail-safe)"""
        try:
            self.services.recorder.record(event)
        except Exception:
            # Don't fail execution if tracing fails
            pass
    
    def _finish_times(self, t0: float) -> tuple[str, int]:
        """Calculate finish time and duration"""
        from failcore.core.types.step import utc_now_iso
        finished_at = utc_now_iso()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        return finished_at, duration_ms


__all__ = ["FailureBuilder"]
