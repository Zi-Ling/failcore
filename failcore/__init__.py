# failcore/__init__.py
"""
FailCore - Observable and replayable tool execution engine

Quick Start (Recommended):
    >>> from failcore import run, guard
    >>> 
    >>> with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
    ...     @guard()
    ...     def write_file(path: str, content: str):
    ...         with open(path, "w") as f:
    ...             f.write(content)
    ...     
    ...     write_file(path="a.txt", content="hi")
    ...     print(ctx.trace_path)

For advanced usage, import from submodules:
    >>> from failcore.core.step import StepResult, StepStatus
    >>> from failcore.core.executor import Executor
"""

__version__ = "0.1.3"

# Public API
from .api import run
from .api import guard

# Internal components - kept for backward compatibility
from .core.executor.executor import Executor, ExecutorConfig
from .core.tools.registry import ToolRegistry
from .core.validate import ValidatorRegistry
from .core.policy.policy import Policy
from .core.trace.recorder import TraceRecorder, JsonlTraceRecorder, NullTraceRecorder

__all__ = [
    "__version__",
    "run",
    "guard",
]
