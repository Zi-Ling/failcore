# failcore/core/replay/drift/types.py
"""
Drift Module Types

Unified result types for Drift engine (Real and NoOp).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class DriftSeverity(str, Enum):
    """Drift severity level"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class DriftDelta:
    """Single parameter drift delta"""
    path: str  # JSONPath to parameter
    old_value: Any
    new_value: Any
    change_type: str  # "value_changed", "magnitude_changed", "domain_changed"
    magnitude: float = 1.0  # Magnitude of change (1.0 = no change, 2.0 = 2x)


@dataclass(frozen=True)
class DriftResult:
    """
    Drift detection result
    
    Used by both RealDriftEngine and NoOpDriftEngine.
    NoOp returns no drift with reason="disabled".
    """
    drifted: bool = False
    score: float = 0.0
    severity: DriftSeverity = DriftSeverity.NONE
    deltas: List[DriftDelta] = field(default_factory=list)
    reason: str = "ok"  # "ok", "disabled", "error"
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_disabled(self) -> bool:
        """Check if drift detection is disabled (NoOp)"""
        return self.reason == "disabled"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "drifted": self.drifted,
            "score": self.score,
            "severity": self.severity.value,
            "deltas": [
                {
                    "path": d.path,
                    "old_value": str(d.old_value)[:100],
                    "new_value": str(d.new_value)[:100],
                    "change_type": d.change_type,
                    "magnitude": d.magnitude,
                }
                for d in self.deltas
            ],
            "reason": self.reason,
            "evidence": self.evidence,
        }


__all__ = [
    "DriftSeverity",
    "DriftDelta",
    "DriftResult",
]
