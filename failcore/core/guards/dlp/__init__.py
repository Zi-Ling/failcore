"""
Data Loss Prevention (DLP)

Active defense module that intercepts sensitive data leakage at tool call boundaries

NOTE: Uses unified rule system from failcore.core.rules.
Pattern definitions are in config/rulesets/default/dlp.yml (YAML-based).
"""

from failcore.core.rules import RuleCategory, RuleSeverity, RuleRegistry, RuleEngine
from .policies import DLPAction, DLPPolicy, PolicyMatrix
from .middleware import DLPMiddleware

# Legacy PatternCategory mapping for backward compatibility
# Maps to RuleCategory enum values
class PatternCategory:
    """Legacy PatternCategory enum - maps to RuleCategory"""
    API_KEY = "dlp.api_key"
    SECRET_TOKEN = "dlp.secret"
    PRIVATE_KEY = "dlp.secret"
    PII_EMAIL = "dlp.pii"
    PII_PHONE = "dlp.pii"
    PII_SSN = "dlp.pii"
    PAYMENT_CARD = "dlp.payment"

__all__ = [
    "DLPAction",
    "DLPPolicy",
    "PolicyMatrix",
    "PatternCategory",  # Legacy compatibility
    "RuleCategory",
    "RuleSeverity",
    "RuleRegistry",
    "RuleEngine",
    "DLPMiddleware",
]
