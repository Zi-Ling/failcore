# failcore/core/bootstrap/standard.py

"""
Standard bootstrap for Failcore.

This defines the canonical way to assemble:
- Executor
- Policy
- TraceRecorder

It is strict, fail-fast, and intended as the reference wiring.
"""

from failcore.core.executor.executor import Executor
from failcore.core.trace.recorder import JsonlTraceRecorder
from failcore.core.tools.provider import ToolProvider
from failcore.core.tools.registry import ToolRegistry

def create_standard_executor(
    trace_path: str = "trace.jsonl",
    *,
    tools: ToolProvider | None = None,
) -> Executor:
    recorder = JsonlTraceRecorder(trace_path)
    tools = tools or ToolRegistry()   # 没传就给一个空 registry
    return Executor(tools=tools, recorder=recorder)