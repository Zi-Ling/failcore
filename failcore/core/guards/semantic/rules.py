"""
Semantic Guard - Rule Definitions (DEPRECATED)

This module is deprecated. All rule definitions have been moved to:
    from failcore.core.rules import SemanticRule, RuleCategory, RuleSeverity, RuleRegistry

This module now re-exports from rules/ for backward compatibility.
"""

# Re-export from rules (single source of truth)
from failcore.core.rules.semantic import (
    SemanticRule,
    RuleCategory,
    RuleSeverity,
    RuleRegistry,
    BUILTIN_RULES,
)

__all__ = [
    "SemanticRule",
    "RuleCategory",
    "RuleSeverity",
    "RuleRegistry",
    "BUILTIN_RULES",
]
