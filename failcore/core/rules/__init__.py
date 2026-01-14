# failcore/core/rules/__init__.py
"""
Unified Rule System

Provides a unified rule system for all guard modules (DLP, Semantic, Effects, Taint, Drift)
"""

from .models import (
    RuleSeverity,
    RuleCategory,
    RuleAction,
    RuleMetadata,
    Pattern,
    Rule,
    RuleSet,
    PolicyMatrix,
    ThresholdConfig,
    ToolMapping,
)

from .loader import (
    RuleSetLoader,
    CompositeLoader,
)

from .registry import (
    RuleRegistry,
)

from .engine import (
    RuleMatch,
    RuleEngineResult,
    RuleEngine,
)

__all__ = [
    # New unified system
    "RuleSeverity",
    "RuleCategory",
    "RuleAction",
    "RuleMetadata",
    "Pattern",
    "Rule",
    "RuleSet",
    "PolicyMatrix",
    "ThresholdConfig",
    "ToolMapping",
    "RuleSetLoader",
    "CompositeLoader",
    "RuleRegistry",
    "RuleMatch",
    "RuleEngineResult",
    "RuleEngine",
]
