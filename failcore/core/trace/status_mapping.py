# failcore/core/trace/status_mapping.py
"""
Status Mapping - explicit conversion between execution and trace status

This module provides explicit mapping functions to convert between:
- StepStatus (execution-level): ok/fail/blocked
- TraceStepStatus (event-level): ok/fail/blocked/skipped/replayed

Design principle:
- Execution status represents the actual execution result
- Trace status represents how the step appears in trace events
- Explicit mapping prevents semantic confusion and enables trace extensions
"""

from failcore.core.types.step import StepStatus
from .events import TraceStepStatus


def map_step_status_to_trace(
    step_status: StepStatus,
    trace_context: dict = None,
) -> TraceStepStatus:
    """
    Map execution-level StepStatus to trace-level TraceStepStatus
    
    Args:
        step_status: Execution-level status from StepResult
        trace_context: Optional context dict with trace-specific info
            - "replayed": bool - if True, map to REPLAYED
            - "skipped": bool - if True, map to SKIPPED
    
    Returns:
        TraceStepStatus appropriate for trace events
    
    Note:
        - Default mapping: ok→ok, fail→fail, blocked→blocked
        - Trace-specific states (replayed/skipped) override based on context
    """
    # Check trace-specific context first
    if trace_context:
        if trace_context.get("replayed"):
            return TraceStepStatus.REPLAYED
        if trace_context.get("skipped"):
            return TraceStepStatus.SKIPPED
    
    # Default mapping: execution status → trace status
    if step_status == StepStatus.OK:
        return TraceStepStatus.OK
    elif step_status == StepStatus.FAIL:
        return TraceStepStatus.FAIL
    elif step_status == StepStatus.BLOCKED:
        return TraceStepStatus.BLOCKED
    elif step_status == StepStatus.SKIPPED:
        return TraceStepStatus.SKIPPED
    else:
        # Fallback: use value directly if it matches trace status
        return TraceStepStatus(step_status.value)


__all__ = [
    "map_step_status_to_trace",
]
