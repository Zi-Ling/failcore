# failcore/core/egress/engine.py
"""
Egress Engine - Unified execution egress event bus

All execution egress flows through this engine.
Entry points (MCP/Proxy/SDK) emit EgressEvent → Engine → Sinks/Enrichers
"""

from __future__ import annotations
from typing import List, Optional, Any, Dict
import logging

from .types import EgressEvent, EgressType
from .sinks.trace_sink import TraceSink


logger = logging.getLogger(__name__)


class EgressEngine:
    """
    Unified egress event engine
    
    Responsibilities:
    - Accept EgressEvent from any entry point
    - Run enrichers (usage/dlp/taint)
    - Dispatch to sinks (trace/audit/metrics)
    
    Design:
    - Synchronous for v1 (simple, reliable)
    - Queue-based async for v2 (performance)
    - Fail-open: errors in sinks must not block execution
    """
    
    def __init__(
        self,
        trace_sink: Optional[TraceSink] = None,
        enrichers: Optional[List[Any]] = None,
    ):
        self.trace_sink = trace_sink
        self.enrichers = enrichers or []
    
    def emit(self, event: EgressEvent) -> None:
        """
        Emit egress event through pipeline
        
        Pipeline:
        1. Run enrichers (modify event.evidence in-place)
        2. Dispatch to sinks (trace/audit/metrics)
        
        Args:
            event: Egress event to emit
        """
        try:
            # Phase 1: Enrich event
            for enricher in self.enrichers:
                try:
                    enricher.enrich(event)
                except Exception as e:
                    # Enricher failures are non-fatal
                    logger.warning(f"Enricher {enricher.__class__.__name__} failed: {e}")
            
            # Phase 2: Dispatch to sinks
            if self.trace_sink:
                try:
                    self.trace_sink.write(event)
                except Exception as e:
                    # Sink failures are non-fatal
                    logger.error(f"TraceSink write failed: {e}")
        
        except Exception as e:
            # Engine must never block execution
            logger.error(f"EgressEngine.emit failed: {e}")
    
    def flush(self) -> None:
        """Flush all sinks"""
        if self.trace_sink:
            try:
                self.trace_sink.flush()
            except Exception as e:
                logger.error(f"TraceSink flush failed: {e}")
    
    def close(self) -> None:
        """Close all sinks"""
        if self.trace_sink:
            try:
                self.trace_sink.close()
            except Exception as e:
                logger.error(f"TraceSink close failed: {e}")


__all__ = ["EgressEngine"]
