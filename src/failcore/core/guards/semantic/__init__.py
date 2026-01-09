"""
Semantic Intent Guard

High-confidence semantic validation for tool calls.
Only covers extremely rare, 100% malicious scenarios:
- Secret leakage
- Parameter pollution
- Dangerous command combinations

Default: DISABLED. Enable only when needed.
All verdicts are explainable and auditable.

NOTE: Rule definitions moved to core/rules for sharing. Import from:
    from failcore.core.rules import SemanticRule, RuleRegistry, RuleSeverity
"""

from .rules import SemanticRule, RuleCategory, RuleSeverity, RuleRegistry
from .detectors import SemanticDetector
from .verdict import SemanticVerdict, VerdictAction
from .middleware import SemanticGuardMiddleware

__all__ = [
    "SemanticRule",
    "RuleCategory",
    "RuleSeverity",
    "RuleRegistry",
    "SemanticDetector",
    "SemanticVerdict",
    "VerdictAction",
    "SemanticGuardMiddleware",
]
