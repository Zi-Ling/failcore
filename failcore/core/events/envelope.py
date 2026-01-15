"""
Trace Envelope - Unified trace event wrapper

Wraps both ATTEMPT and EGRESS events in consistent envelope format.
Ensures trace is parseable and events are correlatable.
"""

from __future__ import annotations

from typing import Optional, Any, Dict, Union
from dataclasses import dataclass
from enum import Enum

from .attempt import AttemptEvent
from .egress import EgressEvent


class EventType(str, Enum):
    """Event types in trace"""
    ATTEMPT = "ATTEMPT"      # Pre-execution attempt event
    EGRESS = "EGRESS"        # Post-execution egress event
    RUN_START = "RUN_START"  # Run lifecycle
    RUN_END = "RUN_END"


@dataclass
class TraceEnvelope:
    """
    Trace envelope - consistent wrapper for all events
    
    Schema: failcore.trace.v0.2.0 (new version for unified model)
    
    Design:
    - All events wrapped in same envelope structure
    - Envelope provides sequencing, timing, metadata
    - Event payload in 'event' field
    
    Usage:
    ```python
    envelope = TraceEnvelope(
        event_type=EventType.ATTEMPT,
        event=attempt_event,
        run_id="run123",
        seq=1,
    )
    ```
    """
    schema: str = "failcore.trace.v0.2.0"
    seq: int = 0
    ts: str = ""
    level: str = "INFO"
    
    # Event type and payload
    event_type: EventType = EventType.EGRESS
    event: Union[AttemptEvent, EgressEvent, Dict[str, Any]] = None
    
    # Context
    run_id: str = ""
    step_id: Optional[str] = None
    attempt_id: Optional[str] = None
    
    # Metadata
    run: Optional[Dict[str, Any]] = None
    host: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSONL serialization"""
        data = {
            "schema": self.schema,
            "seq": self.seq,
            "ts": self.ts,
            "level": self.level,
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
        }
        
        # Serialize event payload
        if isinstance(self.event, (AttemptEvent, EgressEvent)):
            data["event"] = self.event.to_dict()
        elif isinstance(self.event, dict):
            data["event"] = self.event
        
        # Add context
        if self.run_id:
            data["run_id"] = self.run_id
        if self.step_id:
            data["step_id"] = self.step_id
        if self.attempt_id:
            data["attempt_id"] = self.attempt_id
        
        if self.run:
            data["run"] = self.run
        if self.host:
            data["host"] = self.host
        
        return data


__all__ = ["TraceEnvelope", "EventType"]
