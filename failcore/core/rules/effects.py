"""
Effects Rules - Neutral side-effect type definitions

Shared by both gates (for blocking decisions) and enrichers (for evidence tagging)
"""

# Re-export from guards/effects for now to maintain compatibility
# TODO: Move type definitions here and make guards/effects import from rules
from failcore.core.guards.effects.side_effects import (
    SideEffectType,
    SideEffectCategory,
)

__all__ = [
    "SideEffectType",
    "SideEffectCategory",
]
