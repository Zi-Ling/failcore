# failcore/core/audit/events.py
"""
Side-Effect Events - event records for side-effect tracking

This module defines data structures for representing side-effect events.
These events are used for audit, enforcement, and trace recording.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from failcore.core.guards.effects.side_effects import SideEffectType
from failcore.core.trace.events import SideEffectInfo


@dataclass
class SideEffectEvent:
    """
    Side-effect event record
    
    Represents a single side-effect that occurred during execution.
    """
    type: SideEffectType
    target: Optional[str] = None
    tool: Optional[str] = None
    step_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_side_effect_info(self) -> SideEffectInfo:
        """Convert to SideEffectInfo for trace event"""
        from failcore.core.guards.effects.side_effects import get_category_for_type
        
        if isinstance(self.type, SideEffectType):
            category = get_category_for_type(self.type).value
            type_str = self.type.value
        else:
            category = str(self.type).split(".", 1)[0] if "." in str(self.type) else None
            type_str = str(self.type)
        
        return SideEffectInfo(
            type=type_str,
            target=self.target,
            category=category,
            tool=self.tool,
            step_id=self.step_id,
            metadata=self.metadata,
        )


__all__ = [
    "SideEffectEvent",
]
