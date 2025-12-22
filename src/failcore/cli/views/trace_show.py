# failcore/cli/views/trace_show.py
"""
TraceShowView - View model for trace display
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class TraceStepView:
    """Single step in trace"""
    ordinal: int
    step_id: str
    tool: str
    status: str
    duration_ms: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    output_summary: Optional[str] = None


@dataclass
class TraceShowSummary:
    """Summary statistics for trace"""
    total_steps: int
    ok: int
    fail: int
    blocked: int
    total_duration_ms: int


@dataclass
class TraceShowMeta:
    """Metadata about the trace"""
    trace_path: str
    run_id: Optional[str] = None
    generated_at: Optional[str] = None


@dataclass
class TraceShowView:
    """
    Complete view model for trace display
    
    Represents a trace execution timeline.
    """
    meta: TraceShowMeta
    summary: TraceShowSummary
    steps: List[TraceStepView]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "meta": {
                "trace_path": self.meta.trace_path,
                "run_id": self.meta.run_id,
                "generated_at": self.meta.generated_at,
            },
            "summary": {
                "total_steps": self.summary.total_steps,
                "ok": self.summary.ok,
                "fail": self.summary.fail,
                "blocked": self.summary.blocked,
                "total_duration_ms": self.summary.total_duration_ms,
            },
            "steps": [
                {
                    "ordinal": s.ordinal,
                    "step_id": s.step_id,
                    "tool": s.tool,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "error_code": s.error_code,
                    "error_message": s.error_message,
                    "output_summary": s.output_summary,
                }
                for s in self.steps
            ],
        }
