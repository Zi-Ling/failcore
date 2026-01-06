# failcore/core/replay/drift/types.py
"""
Parameter Drift Types - data structures for parameter snapshots and drift points

Lightweight dataclass/TypedDict for parameter snapshots extracted from trace events
and drift points computed from comparisons.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class ParamSnapshot:
    """
    Parameter snapshot extracted from a trace event
    
    Represents a single tool call's parameters at a point in time.
    Used for drift detection by comparing snapshots against a baseline.
    """
    tool_name: str  # Tool name
    params: Dict[str, Any]  # Original parameters (as extracted from trace)
    seq: int  # Sequence number (step sequence)
    ts: str  # ISO timestamp
    fingerprint: Optional[Dict[str, Any]] = None  # Fingerprint if available
    step_id: Optional[str] = None  # Step ID if available
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "seq": self.seq,
            "ts": self.ts,
            "fingerprint": self.fingerprint,
            "step_id": self.step_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParamSnapshot":
        """Create from dictionary"""
        return cls(
            tool_name=data["tool_name"],
            params=data["params"],
            seq=data["seq"],
            ts=data["ts"],
            fingerprint=data.get("fingerprint"),
            step_id=data.get("step_id"),
        )


@dataclass
class DriftChange:
    """
    Single field change detected in drift comparison
    
    Represents one field's deviation from baseline.
    """
    field_path: str  # Field path (e.g., "path", "recursive", "options.timeout")
    baseline_value: Any  # Baseline value
    current_value: Any  # Current value
    change_type: str  # "value_changed", "magnitude_changed", "domain_changed"
    severity: str  # "low", "medium", "high"
    reason: str  # Human-readable reason for the change
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "field_path": self.field_path,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "change_type": self.change_type,
            "severity": self.severity,
            "reason": self.reason,
        }


@dataclass
class DriftPoint:
    """
    Drift point computed for a single step
    
    Represents drift score and changes at a specific point in execution.
    Aligned with ParamSnapshot structure for traceability.
    """
    seq: int  # Sequence number (matches ParamSnapshot.seq)
    ts: str  # ISO timestamp (matches ParamSnapshot.ts)
    tool: str  # Tool name (matches ParamSnapshot.tool_name)
    drift_delta: float  # Drift score for this step (relative to baseline)
    drift_cumulative: float  # Cumulative drift score up to this step
    top_changes: List[DriftChange] = field(default_factory=list)  # Top changes detected
    step_id: Optional[str] = None  # Step ID if available
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "tool": self.tool,
            "drift_delta": self.drift_delta,
            "drift_cumulative": self.drift_cumulative,
            "top_changes": [c.to_dict() for c in self.top_changes],
            "step_id": self.step_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DriftPoint":
        """Create from dictionary"""
        return cls(
            seq=data["seq"],
            ts=data["ts"],
            tool=data["tool"],
            drift_delta=data["drift_delta"],
            drift_cumulative=data["drift_cumulative"],
            top_changes=[DriftChange(**c) for c in data.get("top_changes", [])],
            step_id=data.get("step_id"),
        )


@dataclass
class DriftAnnotation:
    """
    UI-friendly annotation for drift display in replay viewer
    
    Represents a single drift annotation that can be displayed as a badge/tooltip.
    """
    badge: str  # "DRIFT" or "INFLECTION"
    severity: str  # "info", "warn", "high"
    summary: str  # One-line summary (e.g., "param domain changed: path /tmp → /etc")
    changes: List[Dict[str, Any]] = field(default_factory=list)  # Top 3 field changes for tooltip/diff
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "badge": self.badge,
            "severity": self.severity,
            "summary": self.summary,
            "changes": self.changes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DriftAnnotation":
        """Create from dictionary"""
        return cls(
            badge=data["badge"],
            severity=data["severity"],
            summary=data["summary"],
            changes=data.get("changes", []),
        )


__all__ = ["ParamSnapshot", "DriftChange", "DriftPoint", "DriftAnnotation"]
