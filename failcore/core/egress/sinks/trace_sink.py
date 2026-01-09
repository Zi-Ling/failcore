# failcore/core/egress/sinks/trace_sink.py
"""
Trace Sink - Thin compatibility wrapper over EventWriter

DEPRECATED: Direct use of TraceSink is discouraged.
New code should use EventWriter directly.

This module provides backward compatibility for existing code.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Any

from failcore.core.trace.writer import EventWriter
from ..types import EgressEvent


class TraceSink:
    """
    Compatibility wrapper for EventWriter
    
    Maintains backward compatibility with existing EgressEngine code.
    All writes are forwarded to EventWriter with v0.1.3 envelope format.
    
    Migration path:
    - Phase 1: TraceSink wraps EventWriter (current)
    - Phase 2: Update all callers to use EventWriter directly
    - Phase 3: Remove TraceSink entirely
    """
    
    def __init__(
        self,
        trace_path: str | Path,
        *,
        async_mode: bool = False,  # Ignored - kept for compatibility
        buffer_size: int = 1,
        flush_interval_s: float = 0.0,
        run_id: str = "unknown",  # Required for EventWriter
        kind: str = "run",  # "run", "proxy", "mcp"
    ):
        """
        Initialize TraceSink (compatibility wrapper)
        
        Args:
            trace_path: Path to trace.jsonl
            async_mode: Ignored (EventWriter is always thread-safe)
            buffer_size: Buffer size for EventWriter
            flush_interval_s: Flush interval for EventWriter
            run_id: Run identifier (required)
            kind: Run kind (run/proxy/mcp)
        """
        self.trace_path = Path(trace_path)
        self.run_id = run_id
        self.kind = kind
        
        # Create underlying EventWriter
        self._writer = EventWriter(
            trace_path=self.trace_path,
            run_id=self.run_id,
            kind=self.kind,
            buffer_size=buffer_size,
            flush_interval_s=flush_interval_s,
        )
    
    def write(self, event: EgressEvent) -> None:
        """
        Write egress event to trace
        
        Args:
            event: EgressEvent to write
        """
        # Forward to EventWriter
        self._writer.write_egress_event(event)
    
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
