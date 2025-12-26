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
from failcore.core.trace.recorder import JsonlTraceRecorder, CompositeTraceRecorder
from failcore.core.tools.provider import ToolProvider
from failcore.core.tools.registry import ToolRegistry
from failcore.infra.observability.otel.writer import OtelWriter

def create_standard_executor(
    trace_path: str = "trace.jsonl",
    *,
    tools: ToolProvider | None = None,
) -> Executor:
    # Primary recorder (authoritative, strict)
    primary = JsonlTraceRecorder(trace_path)

    # Optional OTel recorder (best-effort)
    otel_recorder = None
    try:
        from failcore.infra.observability.otel.writer import OtelWriter

        otel_writer = OtelWriter.try_from_env()
        if otel_writer is not None:
            class _OtelRecorderAdapter:
                def __init__(self, writer):
                    self._writer = writer

                def record(self, event) -> None:
                    self._writer.write(event)

            otel_recorder = _OtelRecorderAdapter(otel_writer)
    except Exception:
        # OTel is strictly optional
        otel_recorder = None

    # Compose recorders if OTel is enabled
    if otel_recorder is not None:
        recorder = CompositeTraceRecorder(primary, [otel_recorder])
    else:
        recorder = primary

    tools = tools or ToolRegistry()
    return Executor(tools=tools, recorder=recorder)