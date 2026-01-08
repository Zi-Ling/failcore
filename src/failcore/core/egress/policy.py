# failcore/core/egress/policy.py
"""
Policy Decision Integration for Egress

Converts existing PolicyResult to EgressEvent-compatible decisions.
"""

from typing import Optional
from .types import PolicyDecision, RiskLevel


def normalize_policy_decision(
    allowed: bool,
    reason: str = "",
    error_code: Optional[str] = None,
) -> tuple[PolicyDecision, RiskLevel]:
    """
    Normalize policy result to egress decision
    
    Args:
        allowed: Policy allow/deny
        reason: Reason text
        error_code: Error code if denied
    
    Returns:
        Tuple of (PolicyDecision, RiskLevel)
    """
    if allowed:
        return PolicyDecision.ALLOW, RiskLevel.LOW
    
    # Assess risk based on error code
    high_risk_codes = {
        "PATH_TRAVERSAL",
        "SSRF_BLOCKED",
        "EXECUTION_TIMEOUT",
        "SANDBOX_VIOLATION",
    }
    
    if error_code in high_risk_codes:
        risk = RiskLevel.HIGH
    else:
        risk = RiskLevel.MEDIUM
    
    return PolicyDecision.DENY, risk


__all__ = ["normalize_policy_decision"]
