"""
Semantic Rules - Neutral semantic rule definitions

Shared by both gates (for blocking decisions) and enrichers (for evidence tagging)
"""

# Re-export from guards/semantic for now to maintain compatibility
# TODO: Move rule definitions here and make guards/semantic import from rules
from failcore.core.guards.semantic.rules import (
    SemanticRule,
    RuleCategory,
    RuleSeverity,
    RuleRegistry,
)

__all__ = [
    "SemanticRule",
    "RuleCategory",
    "RuleSeverity",
    "RuleRegistry",
]
