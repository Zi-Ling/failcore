"""
DLP Pattern Registry (DEPRECATED)

This module is deprecated. All pattern definitions have been moved to:
    from failcore.core.rules import DLPPatternRegistry, SensitivePattern, PatternCategory

This module now re-exports from rules/ for backward compatibility.
"""

from __future__ import annotations

# Re-export from rules (single source of truth)
from failcore.core.rules.dlp import (
    DLPPatternRegistry,
    SensitivePattern,
    PatternCategory,
)

__all__ = [
    "DLPPatternRegistry",
    "SensitivePattern",
    "PatternCategory",
]
