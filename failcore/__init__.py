# failcore/__init__.py
"""
FailCore - Observable and replayable tool execution engine

User-facing API (recommended):
- run(): Run API - one-line execution for quick testing and single-step operations
- Session: Session API - recommended main entry point for real usage
- Result: Execution result (alias of StepResult)
- presets: Presets collection (validators, policy, tools)

Advanced/Internal API (for integrators and framework authors):
- core.*: Core components (Executor, Step, Policy, Validator, etc.)
- adapters.*: Adapters (langchain, etc.)

Basic usage:

Run API (single-step execution):
    >>> from failcore import run
    >>> result = run("divide", a=6, b=2, trace="trace.jsonl")
    >>> print(result.output.value)

Session API (recommended):
    >>> from failcore import Session
    >>> session = Session(trace="trace.jsonl")
    >>> session.register("divide", lambda a, b: a / b)
    >>> result = session.call("divide", a=6, b=2)
    >>> print(result.status, result.output.value)

Decorator style:
    >>> session = Session()
    >>> @session.tool
    ... def add(a: int, b: int) -> int:
    ...     return a + b
    >>> result = session.call("add", a=1, b=2)

Presets:
    >>> from failcore import Session, presets
    >>> session = Session(
    ...     validator=presets.fs_safe(),
    ...     policy=presets.read_only()
    ... )

Context Manager:
    >>> with Session(trace="trace.jsonl") as session:
    ...     session.register("divide", lambda a, b: a / b)
    ...     result = session.call("divide", a=6, b=2)
"""

__version__ = "0.1.0"

# User-facing API (main entry point)
from .api import run, Session, Result, presets, watch, set_watch_session, WatchContext

# Core types (optional imports)
from .core.step import (
    Step,
    StepResult,
    StepStatus,
    StepError,
    StepOutput,
    RunContext,
    OutputKind,
    ArtifactRef,
)

# Advanced components (for integrators)
from .core.executor.executor import Executor, ExecutorConfig
from .core.tools.registry import ToolRegistry
from .core.validate.validator import ValidatorRegistry
from .core.policy.policy import Policy
from .core.trace.recorder import TraceRecorder, JsonlTraceRecorder, NullTraceRecorder

__all__ = [
    # Version
    "__version__",
    
    # User-facing API (recommended)
    "run",
    "Session",
    "Result",
    "presets",
    "watch",
    "set_watch_session",
    "WatchContext",
    
    # Core types
    "Step",
    "StepResult",
    "StepStatus",
    "StepError",
    "StepOutput",
    "RunContext",
    "OutputKind",
    "ArtifactRef",
    
    # Advanced components
    "Executor",
    "ExecutorConfig",
    "ToolRegistry",
    "ValidatorRegistry",
    "Policy",
    "TraceRecorder",
    "JsonlTraceRecorder",
    "NullTraceRecorder",
]
