# failcore/core/trace/__init__.py
from .events import (
    TraceEvent,
    EventType,
    LogLevel,
    StepStatus,
    ExecutionPhase,
    RunContext,
    StepInfo,
    PayloadInfo,
    ResultInfo,
    PolicyInfo,
    ValidationInfo,
    NormalizeInfo,
    ArtifactInfo,
    utc_now_iso,
)
from .recorder import TraceRecorder, JsonlTraceRecorder, NullTraceRecorder
from .builder import (
    build_run_start_event,
    build_run_end_event,
    build_step_start_event,
    build_step_end_event,
    build_policy_denied_event,
    build_output_normalized_event,
    build_run_context,
)

__all__ = [
    # Events
    "TraceEvent",
    "EventType",
    "LogLevel",
    "StepStatus",
    "ExecutionPhase",
    # Data models
    "RunContext",
    "StepInfo",
    "PayloadInfo",
    "ResultInfo",
    "PolicyInfo",
    "ValidationInfo",
    "NormalizeInfo",
    "ArtifactInfo",
    # Utilities
    "utc_now_iso",
    # Recorders
    "TraceRecorder",
    "JsonlTraceRecorder",
    "NullTraceRecorder",
    # Builders
    "build_run_start_event",
    "build_run_end_event",
    "build_step_start_event",
    "build_step_end_event",
    "build_policy_denied_event",
    "build_output_normalized_event",
    "build_run_context",
]
"""
Core trace types for Failcore.

This package defines the components responsible for:
- Recording events
- Serializing events
- Storing events

No side effects on import.
"""

from .recorder import JsonlTraceRecorder

__all__ = [
    "JsonlTraceRecorder",
]
