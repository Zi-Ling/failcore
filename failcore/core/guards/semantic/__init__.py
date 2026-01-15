"""
Semantic Intent Guard

High-confidence semantic validation for tool calls.
Only covers extremely rare, 100% malicious scenarios:
- Secret leakage
- Parameter pollution
- Dangerous command combinations

Default: DISABLED. Enable only when needed.
All verdicts are explainable and auditable.

NOTE: Rule definitions are in config/rulesets/default/semantic.yml (YAML-based).
Use unified rule system from failcore.core.rules.
"""

from failcore.core.rules import RuleCategory, RuleSeverity, RuleRegistry, RuleEngine
from .detectors import SemanticDetector
from .verdict import SemanticVerdict, VerdictAction
from .middleware import SemanticGuardMiddleware

__all__ = [
    "RuleCategory",
    "RuleSeverity",
    "RuleRegistry",
    "RuleEngine",
    "SemanticDetector",
    "SemanticVerdict",
    "VerdictAction",
    "SemanticGuardMiddleware",
]
