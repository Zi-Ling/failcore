# failcore/core/egress/sinks/trace_sink.py
"""
Trace Sink - Unified trace writing for all egress events

Replaces scattered trace write logic with single authoritative sink.
All trace writes go through here.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Any

from failcore.infra.storage.trace_writer import SyncTraceWriter, AsyncTraceWriter
from ..types import EgressEvent


class TraceSink:
    """
    Unified trace sink for EgressEvent
    
    Responsibilities:
    - Single authoritative trace writer
    - Path management
    - Format normalization
    - Buffering and flushing
    
    Design:
    - Wraps existing trace_writer infrastructure
    - Converts EgressEvent → trace format
    - Fail-safe: errors must not propagate
    """
    
    def __init__(
        self,
        trace_path: str | Path,
        *,
        async_mode: bool = False,
        buffer_size: int = 100,
        flush_interval_s: float = 1.0,
    ):
        self.trace_path = Path(trace_path)
        self.async_mode = async_mode
        
        # Create underlying writer
        if async_mode:
            self._writer = AsyncTraceWriter(
                trace_path=self.trace_path,
                buffer_size=buffer_size,
                flush_interval_s=flush_interval_s,
            )
        else:
            self._writer = SyncTraceWriter(
                trace_path=self.trace_path,
                buffer_size=buffer_size,
                flush_interval_s=flush_interval_s,
            )
    
    def write(self, event: EgressEvent) -> None:
        """
        Write egress event to trace
        
        Args:
            event: EgressEvent to write
        """
        # Convert EgressEvent to trace format
        trace_event = self._normalize_to_trace(event)
        
        # Write through underlying writer
        self._writer.write_event(trace_event)
    
    def _normalize_to_trace(self, event: EgressEvent) -> dict[str, Any]:
        """
        Normalize EgressEvent to trace format
        
        This is the single point where egress → trace conversion happens.
        """
        return {
            "type": "egress_event",
            "egress": event.egress.value,
            "action": event.action,
            "target": event.target,
            "run_id": event.run_id,
            "step_id": event.step_id,
            "tool_name": event.tool_name,
            "decision": event.decision.value,
            "risk": event.risk.value,
            "evidence": event.evidence,
            "timestamp": event.timestamp.isoformat(),
            "summary": event.summary or f"{event.action} on {event.target}",
        }
    
    def flush(self) -> None:
        """Flush buffered events"""
        self._writer.flush()
    
    def close(self) -> None:
        """Close writer and flush"""
        self._writer.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = ["TraceSink"]
