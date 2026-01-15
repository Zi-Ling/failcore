# failcore/config/modules/effects.py
"""
Effects Module Configuration

Configuration for Side-Effect Detection module.
"""

from dataclasses import dataclass
from typing import Optional, Literal
from .base import ModuleConfig


@dataclass(frozen=True)
class EffectsConfig(ModuleConfig):
    """
    Effects module configuration.
    
    enabled: If True, effects detection is registered at startup
    boundary_preset: Boundary preset name (strict/permissive/read_only/network_only/none)
    enforce_boundary: If True, enforce boundary (block violations), else only detect
    """
    
    enabled: bool = False
    boundary_preset: Literal["strict", "permissive", "read_only", "network_only", "none"] = "none"
    enforce_boundary: bool = False  # Detection only by default
    
    @classmethod
    def default(cls) -> "EffectsConfig":
        """Default effects configuration"""
        return cls(
            enabled=False,
            boundary_preset="none",
            enforce_boundary=False,
        )
    
    @classmethod
    def strict(cls) -> "EffectsConfig":
        """Strict effects configuration"""
        return cls(
            enabled=True,
            boundary_preset="strict",
            enforce_boundary=True,
        )
