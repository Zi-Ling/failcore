# failcore/web/services/replay_schema.py
"""
Replay Schema - unified data contract for Incident Replay Viewer

Defines the data structure that the Replay Viewer expects.
All services should normalize their output to match this schema.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class StepFrame:
    """
    Single frame in incident replay (represents one tool call step)
    
    Each frame is built from STEP_START + STEP_END events in trace.
    """
    seq: int  # Step sequence number
    ts_start: str  # ISO timestamp of STEP_START
    tool: str  # Tool name
    ts_end: Optional[str] = None  # ISO timestamp of STEP_END (None if not ended)
    status: str = "PENDING"  # "PENDING", "OK", "BLOCKED", "ERROR"
    args: Dict[str, Any] = field(default_factory=dict)  # Tool arguments (normalized)
    args_raw: Optional[Dict[str, Any]] = None  # Original tool arguments (preserved)
    args_diff: Optional[Dict[str, Any]] = None  # Argument changes (if replaying with different args)
    result_summary: Optional[str] = None  # Human-readable result summary
    result_raw: Optional[Any] = None  # Original tool result (preserved)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)  # Anomalies detected in this frame
    decision: Optional[str] = None  # Decision made (e.g., "ALLOWED", "BLOCKED")
    metrics: Optional[Dict[str, Any]] = None  # Cost/metrics for this frame
    evidence: List[Dict[str, Any]] = field(default_factory=list)  # Evidence items (logs, errors, etc.)
    error_code: Optional[str] = None  # Error code if failed/blocked
    error_message: Optional[str] = None  # Error message if failed/blocked
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        # Add tool_metadata if available (not in dataclass, but added dynamically)
        if hasattr(self, '_tool_metadata') and self._tool_metadata:
            result['tool_metadata'] = self._tool_metadata
        return result


@dataclass
class IncidentEvent:
    """
    Event in incident replay (blocked steps, budget exceeded, etc.)
    
    Matches CostEvent structure but extended for replay context.
    """
    type: str  # "blocked", "budget_exceeded", "burn_rate_exceeded", "error", etc.
    seq: int  # Step sequence number
    ts: str  # ISO timestamp
    reason: str  # Human-readable reason
    error_code: Optional[str] = None
    severity: Optional[str] = None  # "low", "medium", "high", "critical"
    context: Optional[Dict[str, Any]] = None  # Additional context
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class RunMeta:
    """
    Metadata about the run
    """
    run_id: str
    command: Optional[str] = None
    workspace: Optional[str] = None
    sandbox_root: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: Optional[str] = None  # "running", "completed", "blocked", "error"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class CostBudget:
    """
    Budget limits applied to the run
    """
    max_cost_usd: Optional[float] = None
    max_tokens: Optional[int] = None
    max_usd_per_minute: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class CostPoint:
    """
    Single point in cost curve
    """
    seq: int
    ts: str
    delta_cost_usd: float
    cum_cost_usd: float
    delta_tokens: int
    cum_tokens: int
    status: str
    tool: str
    error_code: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class IncidentTape:
    """
    Unified data structure for Incident Replay Viewer
    
    This is the single source of truth for replay viewer input.
    All services should normalize their output to match this structure.
    """
    run_id: str
    meta: RunMeta
    frames: List[StepFrame]  # Ordered by seq
    events: List[IncidentEvent]  # Blocked events, errors, etc.
    budget: Optional[CostBudget] = None
    cost_curve: List[CostPoint] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "run_id": self.run_id,
            "meta": self.meta.to_dict(),
            "frames": [f.to_dict() for f in self.frames],
            "events": [e.to_dict() for e in self.events],
            "budget": self.budget.to_dict() if self.budget else None,
            "cost_curve": [p.to_dict() for p in self.cost_curve],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentTape":
        """Create IncidentTape from dictionary"""
        return cls(
            run_id=data["run_id"],
            meta=RunMeta(**data["meta"]),
            frames=[StepFrame(**f) for f in data["frames"]],
            events=[IncidentEvent(**e) for e in data["events"]],
            budget=CostBudget(**data["budget"]) if data.get("budget") else None,
            cost_curve=[CostPoint(**p) for p in data.get("cost_curve", [])],
        )


# Type aliases for convenience
AnomalyDict = Dict[str, Any]  # {field_path, severity, reason, explanation, risk_type}
EvidenceDict = Dict[str, Any]  # {type, ts, message, data}


__all__ = [
    "StepFrame",
    "IncidentEvent",
    "RunMeta",
    "CostBudget",
    "CostPoint",
    "IncidentTape",
    "AnomalyDict",
    "EvidenceDict",
]
