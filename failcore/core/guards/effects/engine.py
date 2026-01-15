# failcore/core/guards/effects/engine.py
"""
Effects Engine

Real and NoOp implementations of side-effect detection engine.
"""

from typing import Dict, Any
from .types import EffectsResult, SideEffect, EffectCategory, EffectType
from failcore.core.guards.effects.detection import (
    detect_filesystem_side_effect,
    detect_network_side_effect,
    detect_exec_side_effect,
)


class EffectsEngine:
    """
    Side-effect detection engine interface
    
    Both RealEffectsEngine and NoOpEffectsEngine implement this interface.
    """
    
    def detect(self, tool_name: str, params: Dict[str, Any]) -> EffectsResult:
        """
        Detect side effects from tool call
        
        Args:
            tool_name: Tool name
            params: Tool parameters
        
        Returns:
            EffectsResult with detected effects
        """
        raise NotImplementedError


class RealEffectsEngine(EffectsEngine):
    """
    Real Effects engine implementation
    
    Uses heuristic detection to predict side effects.
    """
    
    def __init__(self, boundary=None):
        """
        Initialize real Effects engine
        
        Args:
            boundary: Optional side-effect boundary for enforcement
        """
        self.boundary = boundary
    
    def detect(self, tool_name: str, params: Dict[str, Any]) -> EffectsResult:
        """Detect side effects using heuristics"""
        effects = []
        
        # Detect filesystem effects
        fs_effect = detect_filesystem_side_effect(tool_name, params)
        if fs_effect:
            category = EffectCategory.FILESYSTEM
            effect_type = EffectType.FS_WRITE if "write" in tool_name.lower() else EffectType.FS_READ
            target = params.get("path", params.get("file", ""))
            effects.append(SideEffect(
                category=category,
                effect_type=effect_type,
                tool_name=tool_name,
                target=target,
                confidence=0.8,  # Heuristic confidence
            ))
        
        # Detect network effects
        net_effect = detect_network_side_effect(tool_name, params)
        if net_effect:
            category = EffectCategory.NETWORK
            effect_type = EffectType.NET_EGRESS
            target = params.get("url", params.get("endpoint", ""))
            effects.append(SideEffect(
                category=category,
                effect_type=effect_type,
                tool_name=tool_name,
                target=target,
                confidence=0.8,
            ))
        
        # Detect exec effects
        exec_effect = detect_exec_side_effect(tool_name, params)
        if exec_effect:
            category = EffectCategory.EXEC
            effect_type = EffectType.EXEC_SPAWN
            target = params.get("command", params.get("cmd", ""))
            effects.append(SideEffect(
                category=category,
                effect_type=effect_type,
                tool_name=tool_name,
                target=target,
                confidence=0.9,
            ))
        
        return EffectsResult(
            detected=len(effects) > 0,
            effects=effects,
            reason="ok",
            evidence={
                "detection_method": "heuristic",
                "boundary_enforced": self.boundary is not None,
            },
        )


class NoOpEffectsEngine(EffectsEngine):
    """
    NoOp Effects engine when module is disabled
    
    Returns no effects with reason="disabled" for observability.
    """
    
    def detect(self, tool_name: str, params: Dict[str, Any]) -> EffectsResult:
        """NoOp detect - returns no effects"""
        return EffectsResult(
            detected=False,
            effects=[],
            reason="disabled",
            evidence={
                "status": "disabled",
            },
        )
    
    def __repr__(self) -> str:
        return "NoOpEffectsEngine(disabled)"


__all__ = [
    "EffectsEngine",
    "RealEffectsEngine",
    "NoOpEffectsEngine",
]
