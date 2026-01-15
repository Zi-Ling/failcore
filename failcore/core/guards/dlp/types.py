# failcore/core/guards/dlp/types.py
"""
DLP Module Types

Unified result types for DLP engine (Real and NoOp).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Literal
from enum import Enum


class DLPMode(str, Enum):
    """DLP enforcement mode"""
    BLOCK = "block"
    SANITIZE = "sanitize"
    WARN = "warn"


@dataclass(frozen=True)
class DLPFinding:
    """Single DLP pattern match finding"""
    pattern_name: str
    category: str
    severity: int
    matched_text: str
    position: int = -1  # Character position in text


@dataclass(frozen=True)
class DLPResult:
    """
    DLP scan result
    
    Used by both RealDlpEngine and NoOpDlpEngine.
    NoOp returns empty matches with reason="disabled".
    """
    matches: List[DLPFinding] = field(default_factory=list)
    match_count: int = 0
    max_severity: int = 0
    reason: str = "ok"  # "ok", "disabled", "error"
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_matches(self) -> bool:
        """Check if any matches found"""
        return self.match_count > 0
    
    @property
    def is_disabled(self) -> bool:
        """Check if DLP is disabled (NoOp)"""
        return self.reason == "disabled"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "matches": [
                {
                    "pattern_name": f.pattern_name,
                    "category": f.category,
                    "severity": f.severity,
                    "matched_text": f.matched_text[:50],  # Truncate
                    "position": f.position,
                }
                for f in self.matches
            ],
            "match_count": self.match_count,
            "max_severity": self.max_severity,
            "reason": self.reason,
            "evidence": self.evidence,
        }


__all__ = [
    "DLPMode",
    "DLPFinding",
    "DLPResult",
]
