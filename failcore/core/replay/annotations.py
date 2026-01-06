# failcore/core/replay/annotations.py
"""
Replay Annotations - side-effect crossing annotations for replay viewer

Converts side-effect boundary crossings into replay-friendly annotations.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..audit.side_effect_auditor import CrossingRecord
from ..audit.side_effects import SideEffectType


@dataclass
class SideEffectCrossingAnnotation:
    """
    Side-effect crossing annotation for replay viewer
    
    Represents a boundary crossing as a replay annotation.
    This makes security events visible in the replay UI.
    """
    badge: str = "CROSSING"  # Badge to display
    severity: str = "high"  # Severity: "info", "warn", "high"
    summary: str = ""  # One-line summary
    crossing_type: str = ""  # Side-effect type
    target: Optional[str] = None  # Target of the crossing
    tool: Optional[str] = None  # Tool that caused crossing
    step_seq: Optional[int] = None  # Step sequence
    allowed_categories: list = field(default_factory=list)  # Allowed categories
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "badge": self.badge,
            "severity": self.severity,
            "summary": self.summary,
            "crossing_type": self.crossing_type,
            "target": self.target,
            "tool": self.tool,
            "step_seq": self.step_seq,
            "allowed_categories": self.allowed_categories,
        }
    
    @classmethod
    def from_crossing_record(cls, crossing: CrossingRecord) -> "SideEffectCrossingAnnotation":
        """
        Create annotation from crossing record
        
        Args:
            crossing: Crossing record
        
        Returns:
            SideEffectCrossingAnnotation
        """
        crossing_type = crossing.crossing_type.value if isinstance(crossing.crossing_type, SideEffectType) else str(crossing.crossing_type)
        target_str = f" -> {crossing.target}" if crossing.target else ""
        allowed_str = ", ".join(crossing.allowed_categories) if crossing.allowed_categories else "none"
        
        summary = f"Boundary crossed: {crossing_type}{target_str}. Allowed: {allowed_str}"
        
        return cls(
            badge="CROSSING",
            severity="high",
            summary=summary,
            crossing_type=crossing_type,
            target=crossing.target,
            tool=crossing.tool,
            step_seq=crossing.step_seq,
            allowed_categories=crossing.allowed_categories,
        )


__all__ = [
    "SideEffectCrossingAnnotation",
]
