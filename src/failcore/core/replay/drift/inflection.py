# failcore/core/replay/drift/inflection.py
"""
Inflection Point Detection - detects sudden changes in drift behavior

An inflection point is where drift suddenly increases significantly.
Minimum implementation using threshold + change rate:
- drift_delta >= threshold_high
- drift_delta >= prev_delta * change_rate
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .types import DriftPoint
from .config import DriftConfig, get_default_config


@dataclass
class InflectionPoint:
    """
    Inflection point detected in drift sequence
    
    Represents a sudden change in drift behavior.
    """
    seq: int  # Sequence number where inflection occurred
    ts: str  # Timestamp
    tool: str  # Tool name
    drift_delta: float  # Drift delta at inflection point
    prev_drift_delta: Optional[float]  # Previous drift delta (if available)
    reason: str  # Human-readable reason for inflection
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "tool": self.tool,
            "drift_delta": self.drift_delta,
            "prev_drift_delta": self.prev_drift_delta,
            "reason": self.reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InflectionPoint":
        """Create from dictionary"""
        return cls(
            seq=data["seq"],
            ts=data["ts"],
            tool=data["tool"],
            drift_delta=data["drift_delta"],
            prev_drift_delta=data.get("prev_drift_delta"),
            reason=data["reason"],
        )


def detect_inflection_points(
    drift_points: List[DriftPoint],
    config: Optional[DriftConfig] = None,
) -> List[InflectionPoint]:
    """
    Detect inflection points in drift sequence
    
    Uses two criteria:
    1. Absolute threshold: drift_delta >= threshold_high
    2. Relative threshold: drift_delta >= prev_delta * change_rate
    
    Args:
        drift_points: List of drift points (ordered by seq)
        config: Optional drift configuration (uses default if None)
    
    Returns:
        List of InflectionPoint objects (can be 0 to N points)
    """
    if config is None:
        config = get_default_config()
    
    inflection_points = []
    
    for i, point in enumerate(drift_points):
        drift_delta = point.drift_delta
        prev_drift_delta = drift_points[i - 1].drift_delta if i > 0 else None
        
        reason = None
        
        # Check absolute threshold
        if drift_delta >= config.inflection_threshold_high:
            reason = f"Drift delta {drift_delta:.1f} >= threshold {config.inflection_threshold_high}"
        
        # Check relative threshold (change rate)
        elif prev_drift_delta is not None and prev_drift_delta > 0:
            change_ratio = drift_delta / prev_drift_delta
            if change_ratio >= config.inflection_change_rate:
                reason = f"Drift delta {drift_delta:.1f} is {change_ratio:.1f}x previous ({prev_drift_delta:.1f})"
        
        # Create inflection point if threshold met
        if reason:
            inflection_point = InflectionPoint(
                seq=point.seq,
                ts=point.ts,
                tool=point.tool,
                drift_delta=drift_delta,
                prev_drift_delta=prev_drift_delta,
                reason=reason,
            )
            inflection_points.append(inflection_point)
    
    return inflection_points


__all__ = ["InflectionPoint", "detect_inflection_points"]
