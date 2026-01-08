"""
P0-1: Lightweight Tracing Model
Minimal trace structure compatible with OTEL
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


@dataclass
class TraceEvent:
    """Single event within a span"""
    timestamp: str
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """
    Minimal span structure (OTEL-compatible)
    
    Compatible with both local (Executor) and remote (ToolRuntime) execution
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: str  # INTERNAL, CLIENT, SERVER
    start_time: str
    end_time: Optional[str] = None
    
    # Execution context
    run_id: str = ""
    call_id: str = ""
    
    # Status
    status: str = "ok"  # ok, fail, blocked, etc. (lowercase to match TraceStepStatus enum)
    status_message: str = ""
    
    # Attributes (OTEL conventions)
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Events within span
    events: List[TraceEvent] = field(default_factory=list)
    
    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add event to span"""
        self.events.append(TraceEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            name=name,
            attributes=attributes or {}
        ))
    
    def set_error(self, error_code: str, message: str, suggestion: str = None):
        """Mark span as error with FailCore error attributes"""
        self.status = "ERROR"
        self.status_message = message
        self.attributes["failcore.error_code"] = error_code
        self.attributes["failcore.error_message"] = message
        if suggestion:
            self.attributes["failcore.suggestion"] = suggestion[:200]  # Truncate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSONL/OTEL export"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "run_id": self.run_id,
            "call_id": self.call_id,
            "status": self.status,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": [
                {
                    "timestamp": e.timestamp,
                    "name": e.name,
                    "attributes": e.attributes
                }
                for e in self.events
            ]
        }


@dataclass
class TraceConfig:
    """Trace configuration"""
    enabled: bool = True
    export_jsonl: bool = True
    export_otel: bool = False
    otel_endpoint: str = "http://localhost:4318/v1/traces"
    
    @classmethod
    def default(cls):
        return cls(enabled=True, export_jsonl=True)


def generate_trace_id() -> str:
    """Generate OTEL-compatible trace ID (32 hex chars)"""
    return uuid.uuid4().hex + uuid.uuid4().hex[:16]


def generate_span_id() -> str:
    """Generate OTEL-compatible span ID (16 hex chars)"""
    return uuid.uuid4().hex[:16]


__all__ = [
    "Span",
    "TraceEvent",
    "TraceConfig",
    "generate_trace_id",
    "generate_span_id",
]
