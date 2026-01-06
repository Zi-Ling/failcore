# failcore/core/policy/enforcement.py
"""
Policy Enforcement - side-effect auditor integration

Integrates side-effect auditor into policy enforcement chain.
When crossing occurs, auditor becomes direct blocking reason.
"""

from typing import Optional, List

from ..audit.boundary import SideEffectBoundary
from ..audit.side_effect_auditor import SideEffectAuditor, CrossingRecord
from ..audit.side_effects import SideEffectType
from ..executor.side_effect_probe import SideEffectProbe, SideEffectEvent
from ..errors.side_effect import SideEffectBoundaryCrossedError
from .policy import PolicyResult


class SideEffectPolicyEnforcer:
    """
    Side-effect policy enforcer
    
    Integrates side-effect auditor into policy enforcement.
    When crossing is detected, raises error directly (no warnings).
    """
    
    def __init__(self, boundary: Optional[SideEffectBoundary] = None):
        """
        Initialize side-effect policy enforcer
        
        Args:
            boundary: Side-effect boundary to enforce (None = no enforcement)
        """
        self.boundary = boundary
        self.auditor = SideEffectAuditor(boundary) if boundary else None
    
    def check_side_effect(
        self,
        side_effect_type: SideEffectType,
        target: Optional[str] = None,
        tool: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> PolicyResult:
        """
        Check if a side-effect is allowed
        
        Args:
            side_effect_type: Side-effect type to check
            target: Target of the side-effect
            tool: Tool that causes the side-effect
            step_id: Step ID
        
        Returns:
            PolicyResult (allowed=True if allowed, allowed=False if crossing)
        
        Raises:
            SideEffectBoundaryCrossedError: If crossing detected and enforcement is enabled
        """
        if not self.auditor:
            # No boundary = allow all
            return PolicyResult.allow(reason="No side-effect boundary configured")
        
        # Check if crossing
        if self.auditor.check_crossing(side_effect_type):
            # Crossing detected - create crossing record
            from ..audit.side_effects import get_category_for_type
            category = get_category_for_type(side_effect_type)
            
            crossing = CrossingRecord(
                crossing_type=side_effect_type,
                boundary=self.boundary,
                target=target,
                tool=tool,
                step_id=step_id,
                observed_category=category.value,
                allowed_categories=[cat.value for cat in self.boundary.allowed_categories],
            )
            
            # Convert to error and raise (direct failure, no warnings)
            raise SideEffectBoundaryCrossedError(crossing)
        
        # Allowed
        return PolicyResult.allow(reason=f"Side-effect {side_effect_type.value} allowed by boundary")
    
    def check_side_effects(
        self,
        side_effect_events: List[SideEffectEvent],
        step_seq: Optional[int] = None,
        ts: Optional[str] = None,
    ) -> List[CrossingRecord]:
        """
        Check multiple side-effect events for crossings
        
        Args:
            side_effect_events: List of side-effect events to check
            step_seq: Step sequence number
            ts: Timestamp
        
        Returns:
            List of crossing records (empty if no crossings)
        
        Note:
            This method returns crossings but does NOT raise errors.
            Use check_side_effect() for per-event enforcement.
        """
        if not self.auditor:
            return []
        
        crossings = self.auditor.detect_crossings(side_effect_events)
        
        # Set step_seq and ts if provided
        for crossing in crossings:
            if step_seq is not None:
                crossing.step_seq = step_seq
            if ts is not None:
                crossing.ts = ts
        
        return crossings


__all__ = [
    "SideEffectPolicyEnforcer",
]
