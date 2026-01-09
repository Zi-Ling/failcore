"""
DLP Rules - Neutral pattern definitions

Shared by both gates (for blocking decisions) and enrichers (for evidence tagging)
"""

# Re-export from guards/dlp/patterns for now to maintain compatibility
# TODO: Move pattern definitions here and make guards/dlp import from rules
from failcore.core.guards.dlp.patterns import (
    DLPPatternRegistry,
    SensitivePattern,
    PatternCategory,
)

__all__ = [
    "DLPPatternRegistry",
    "SensitivePattern",
    "PatternCategory",
]
