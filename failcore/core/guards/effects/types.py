# failcore/core/guards/effects/types.py
"""
Effects Module Types

Unified result types for Effects engine (Real and NoOp).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Literal
from enum import Enum


class EffectCategory(str, Enum):
    """Side effect category"""
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    EXEC = "exec"
    PROCESS = "process"


class EffectType(str, Enum):
    """Side effect type"""
    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    FS_DELETE = "fs_delete"
    NET_EGRESS = "net_egress"
    NET_INGRESS = "net_ingress"
    EXEC_SPAWN = "exec_spawn"
    PROCESS_KILL = "process_kill"


@dataclass(frozen=True)
class SideEffect:
    """Single side effect detection"""
    category: EffectCategory
    effect_type: EffectType
    tool_name: str
    target: str = ""  # File path, URL, command, etc.
    confidence: float = 1.0


@dataclass(frozen=True)
class EffectsResult:
    """
    Effects detection result
    
    Used by both RealEffectsEngine and NoOpEffectsEngine.
    NoOp returns no effects with reason="disabled".
    """
    detected: bool = False
    effects: List[SideEffect] = field(default_factory=list)
    reason: str = "ok"  # "ok", "disabled", "error"
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_disabled(self) -> bool:
        """Check if effects detection is disabled (NoOp)"""
        return self.reason == "disabled"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "detected": self.detected,
            "effects": [
                {
                    "category": e.category.value,
                    "effect_type": e.effect_type.value,
                    "tool_name": e.tool_name,
                    "target": e.target,
                    "confidence": e.confidence,
                }
                for e in self.effects
            ],
            "reason": self.reason,
            "evidence": self.evidence,
        }


__all__ = [
    "EffectCategory",
    "EffectType",
    "SideEffect",
    "EffectsResult",
]
