# failcore/core/config/guards.py
"""
Guard Configuration - controls enforcement guards (semantic, taint, side-effect)

Centralized configuration for enforcement features:
- semantic: Semantic guard validation (default: OFF)
- taint: Taint tracking and DLP (default: OFF)
- side_effect_boundary: Side-effect boundary enforcement (default: OFF)

Note: Guards can BLOCK or MODIFY execution, unlike AnalysisConfig which is read-only.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GuardConfig:
    """Guard feature configuration"""
    semantic: bool = False      # ❌ default OFF
    taint: bool = False         # ❌ default OFF
    # Note: side_effect_boundary is passed as object, not boolean flag
    # (it's a policy object, not just enable/disable)


# Global default configuration
_DEFAULT_GUARD_CONFIG = GuardConfig()


def get_guard_config(config: Optional[GuardConfig] = None) -> GuardConfig:
    """
    Get guard configuration
    
    Args:
        config: Optional custom config (uses default if None)
    
    Returns:
        GuardConfig instance
    """
    return config or _DEFAULT_GUARD_CONFIG


def is_semantic_enabled(config: Optional[GuardConfig] = None) -> bool:
    """Check if semantic guard is enabled"""
    return get_guard_config(config).semantic


def is_taint_enabled(config: Optional[GuardConfig] = None) -> bool:
    """Check if taint tracking/DLP is enabled"""
    return get_guard_config(config).taint


__all__ = [
    "GuardConfig",
    "get_guard_config",
    "is_semantic_enabled",
    "is_taint_enabled",
]
