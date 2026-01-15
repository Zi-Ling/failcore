# failcore/core/guards/semantic/types.py
"""
Semantic Module Types

Unified result types for Semantic engine (Real and NoOp).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class SemanticAction(str, Enum):
    """Semantic verdict action"""
    ALLOW = "allow"
    WARN = "warn"
    LOG = "log"
    BLOCK = "block"


@dataclass(frozen=True)
class SemanticViolation:
    """Single semantic rule violation"""
    rule_id: str
    rule_name: str
    category: str
    severity: str
    description: str


@dataclass(frozen=True)
class SemanticResult:
    """
    Semantic check result
    
    Used by both RealSemanticEngine and NoOpSemanticEngine.
    NoOp returns allow with reason="disabled".
    """
    action: SemanticAction = SemanticAction.ALLOW
    violations: List[SemanticViolation] = field(default_factory=list)
    reason: str = "ok"  # "ok", "disabled", "error"
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_blocked(self) -> bool:
        """Check if action is BLOCK"""
        return self.action == SemanticAction.BLOCK
    
    @property
    def is_disabled(self) -> bool:
        """Check if semantic is disabled (NoOp)"""
        return self.reason == "disabled"
    
    @property
    def has_violations(self) -> bool:
        """Check if has violations"""
        return len(self.violations) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "action": self.action.value,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "category": v.category,
                    "severity": v.severity,
                    "description": v.description,
                }
                for v in self.violations
            ],
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


__all__ = [
    "SemanticAction",
    "SemanticViolation",
    "SemanticResult",
]
