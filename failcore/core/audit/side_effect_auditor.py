# failcore/core/audit/side_effect_auditor.py
"""
Side-Effect Auditor - crossing detection logic

This is the ONLY place in the module that "makes judgments".
Logic is extremely simple and deterministic:
- If observed_side_effect ∉ declared_boundary → crossing
- No weights, no risk scores, no ML
- Every crossing is an audit fact, not a "risk inference"
"""

from typing import List, Optional
from dataclasses import dataclass

from .boundary import SideEffectBoundary
from .side_effects import SideEffectType
from ..executor.side_effect_probe import SideEffectEvent


@dataclass
class CrossingRecord:
    """
    Side-effect boundary crossing record
    
    Represents a single crossing event - an audit fact, not a risk inference.
    """
    crossing_type: SideEffectType  # Type of side-effect that crossed boundary
    boundary: SideEffectBoundary  # Boundary that was crossed
    step_seq: Optional[int] = None  # Step sequence number
    ts: Optional[str] = None  # Timestamp
    target: Optional[str] = None  # Target of the side-effect (path/host/command)
    tool: Optional[str] = None  # Tool that caused the crossing
    step_id: Optional[str] = None  # Step ID
    observed_category: Optional[str] = None  # Observed category
    allowed_categories: List[str] = None  # Allowed categories in boundary
    
    def __post_init__(self):
        if self.allowed_categories is None:
            self.allowed_categories = [cat.value for cat in self.boundary.allowed_categories]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "crossing_type": self.crossing_type.value if isinstance(self.crossing_type, SideEffectType) else str(self.crossing_type),
            "boundary": {
                "allowed_categories": [cat.value for cat in self.boundary.allowed_categories],
                "allowed_types": [t.value for t in self.boundary.allowed_types] if self.boundary.allowed_types else None,
                "blocked_categories": [cat.value for cat in self.boundary.blocked_categories],
                "blocked_types": [t.value for t in self.boundary.blocked_types] if self.boundary.blocked_types else None,
            },
            "step_seq": self.step_seq,
            "ts": self.ts,
            "target": self.target,
            "tool": self.tool,
            "step_id": self.step_id,
            "observed_category": self.observed_category,
            "allowed_categories": self.allowed_categories,
        }


class SideEffectAuditor:
    """
    Side-Effect Auditor
    
    Detects boundary crossings by comparing observed side-effects against declared boundaries.
    Logic is deterministic: observed_side_effect ∉ declared_boundary → crossing
    """
    
    def __init__(self, boundary: SideEffectBoundary):
        """
        Initialize side-effect auditor
        
        Args:
            boundary: Side-effect boundary to enforce
        """
        self.boundary = boundary
    
    def detect_crossings(
        self,
        side_effect_events: List[SideEffectEvent],
    ) -> List[CrossingRecord]:
        """
        Detect boundary crossings from side-effect events
        
        Logic: If observed_side_effect ∉ declared_boundary → crossing
        
        Args:
            side_effect_events: List of observed side-effect events
        
        Returns:
            List of crossing records (empty if no crossings)
        """
        crossings = []
        
        for event in side_effect_events:
            # Check if this side-effect is allowed
            if not self.boundary.is_allowed(event.type):
                # Crossing detected - create record
                from .side_effects import get_category_for_type
                category = get_category_for_type(event.type)
                
                crossing = CrossingRecord(
                    crossing_type=event.type,
                    boundary=self.boundary,
                    step_seq=None,  # Will be set by caller if available
                    ts=None,  # Will be set by caller if available
                    target=event.target,
                    tool=event.tool,
                    step_id=event.step_id,
                    observed_category=category.value,
                    allowed_categories=[cat.value for cat in self.boundary.allowed_categories],
                )
                crossings.append(crossing)
        
        return crossings
    
    def check_crossing(self, side_effect_type: SideEffectType) -> bool:
        """
        Check if a single side-effect type crosses the boundary
        
        Args:
            side_effect_type: Side-effect type to check
        
        Returns:
            True if crossing (not allowed), False if allowed
        """
        return not self.boundary.is_allowed(side_effect_type)


__all__ = [
    "CrossingRecord",
    "SideEffectAuditor",
]
