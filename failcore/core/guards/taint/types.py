# failcore/core/guards/taint/types.py
"""
Taint Module Types

Unified result types for Taint engine (Real and NoOp).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class TaintSource(str, Enum):
    """Taint source type"""
    FILE = "file"
    DATABASE = "database"
    API = "api"
    USER_INPUT = "user_input"
    ENVIRONMENT = "environment"
    SECRET = "secret"


class DataSensitivity(str, Enum):
    """Data sensitivity level"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"
    SECRET = "secret"


@dataclass(frozen=True)
class TaintTag:
    """Taint tag for data tracking"""
    source: TaintSource
    sensitivity: DataSensitivity
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaintResult:
    """
    Taint tracking result
    
    Used by both RealTaintEngine and NoOpTaintEngine.
    NoOp returns no taint with reason="disabled".
    """
    tainted: bool = False
    sources: List[TaintTag] = field(default_factory=list)
    reason: str = "ok"  # "ok", "disabled", "error"
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_disabled(self) -> bool:
        """Check if taint tracking is disabled (NoOp)"""
        return self.reason == "disabled"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tainted": self.tainted,
            "sources": [
                {
                    "source": s.source.value,
                    "sensitivity": s.sensitivity.value,
                    "confidence": s.confidence,
                    "metadata": s.metadata,
                }
                for s in self.sources
            ],
            "reason": self.reason,
            "evidence": self.evidence,
        }


__all__ = [
    "TaintSource",
    "DataSensitivity",
    "TaintTag",
    "TaintResult",
]
