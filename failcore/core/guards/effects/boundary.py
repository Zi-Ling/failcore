# failcore/core/audit/boundary.py
"""
Side-Effect Boundary - declarative specification of allowed side-effects

A boundary is a static set of allowed side-effect categories/types.
Boundaries are run-scoped, immutable, and used for runtime comparison.
"""

from dataclasses import dataclass, field
from typing import Set, Optional

from .side_effects import SideEffectCategory, SideEffectType


@dataclass(frozen=True)
class SideEffectBoundary:
    """
    Side-effect boundary specification
    
    Defines which side-effect categories/types are allowed during a run.
    This is a static, declarative structure - no conditions, no expressions, no DSL.
    
    Attributes:
        allowed_categories: Set of allowed side-effect categories
        allowed_types: Optional set of specific allowed types (if None, all types in categories are allowed)
        blocked_categories: Set of explicitly blocked categories (takes precedence)
        blocked_types: Optional set of explicitly blocked types (takes precedence)
    """
    allowed_categories: Set[SideEffectCategory] = field(default_factory=set)
    allowed_types: Optional[Set[SideEffectType]] = None
    blocked_categories: Set[SideEffectCategory] = field(default_factory=set)
    blocked_types: Optional[Set[SideEffectType]] = None
    
    def is_allowed(self, side_effect_type: SideEffectType) -> bool:
        """
        Check if a side-effect type is allowed
        
        Args:
            side_effect_type: Side-effect type to check
        
        Returns:
            True if allowed, False if blocked
        """
        from .side_effects import get_category_for_type
        category = get_category_for_type(side_effect_type)
        
        # Check explicit blocks first (takes precedence)
        if category in self.blocked_categories:
            return False
        if self.blocked_types and side_effect_type in self.blocked_types:
            return False
        
        # Check if category is allowed
        if category in self.allowed_categories:
            # If specific types are specified, check if this type is included
            if self.allowed_types is not None:
                return side_effect_type in self.allowed_types
            # Otherwise, all types in the category are allowed
            return True
        
        # Not explicitly allowed
        return False
    
    def is_category_allowed(self, category: SideEffectCategory) -> bool:
        """
        Check if a category is allowed (any type in the category)
        
        Args:
            category: Side-effect category to check
        
        Returns:
            True if category is allowed, False otherwise
        """
        # Check explicit blocks first
        if category in self.blocked_categories:
            return False
        
        # Check if category is in allowed set
        return category in self.allowed_categories




__all__ = [
    "SideEffectBoundary",
    "get_category_for_type",
]
