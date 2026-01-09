# failcore/core/trace/base.py
from .events import (
    TraceEvent,
    EventType,
    LogLevel,
    TraceStepStatus,  # Trace-specific status (event-level)
    ExecutionPhase,
    RunContext,
    StepInfo,
    PayloadInfo,
    ResultInfo,
    PolicyInfo,
    ValidationInfo,
    NormalizeInfo,
    ArtifactInfo,
    ReplayInfo,
    utc_now_iso,
)
from .status_mapping import map_step_status_to_trace
from .recorder import TraceRecorder, JsonlTraceRecorder, NullTraceRecorder
from .builder import (
    build_run_start_event,
    build_run_end_event,
    build_attempt_event,
    build_result_event,
    build_policy_denied_event,
    build_output_normalized_event,
    build_replay_hit_event,
    build_replay_miss_event,
    build_replay_policy_diff_event,
    build_replay_output_diff_event,
    build_replay_injected_event,
    build_run_context,
)
from .writer import TraceWriter, TraceContext
from .validator import TraceValidator, ValidationError

__all__ = [
    # Events
    "TraceEvent",
    "EventType",
    "LogLevel",
    "TraceStepStatus",  # Trace-specific status
    "ExecutionPhase",
    # Status mapping
    "map_step_status_to_trace",
    # Data models
    "RunContext",
    "StepInfo",
    "PayloadInfo",
    "ResultInfo",
    "PolicyInfo",
    "ValidationInfo",
    "NormalizeInfo",
    "ArtifactInfo",
    "ReplayInfo",
    # Utilities
    "utc_now_iso",
    # Recorders
    "TraceRecorder",
    "JsonlTraceRecorder",
    "NullTraceRecorder",
    # Builders
    "build_run_start_event",
    "build_run_end_event",
    "build_attempt_event",
    "build_result_event",
    "build_policy_denied_event",
    "build_output_normalized_event",
    "build_replay_hit_event",
    "build_replay_miss_event",
    "build_replay_policy_diff_event",
    "build_replay_output_diff_event",
    "build_replay_injected_event",
    "build_run_context",
    # Writer
    "TraceWriter",
    "TraceContext",
    # Validator
    "TraceValidator",
    "ValidationError",
]
