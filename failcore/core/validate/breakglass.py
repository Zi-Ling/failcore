#failcore/core/validate/breakglass.py
"""
Breakglass Impact Assessment - Evaluate breakglass override impact

Assesses which validators and decisions are affected by breakglass override,
and estimates the impact on enforcement decisions.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from collections import defaultdict

from .contracts import Policy, Decision, DecisionOutcome, EnforcementMode


class BreakglassImpact:
    """
    Impact assessment for breakglass override
    
    Records:
    - Which validators are affected
    - Which decisions are downgraded (BLOCK -> WARN/ALLOW)
    - Estimated impact summary
    """
    
    def __init__(self, policy: Policy):
        """
        Initialize impact assessment
        
        Args:
            policy: Policy with breakglass override
        """
        self.policy = policy
        self.affected_validators: Set[str] = set()
        self.downgraded_decisions: List[Dict[str, Any]] = []
        self.override_mode: Optional[EnforcementMode] = None
        
        if policy.global_override and policy.global_override.enabled:
            self._assess_impact()
    
    def _assess_impact(self) -> None:
        """Assess breakglass impact"""
        override = self.policy.global_override
        if not override or not override.enabled:
            return
        
        # Check if override mode is set (typically BLOCK when breakglass is active)
        # In practice, breakglass enables override which can downgrade decisions
        self.override_mode = EnforcementMode.BLOCK  # Breakglass typically allows overrides
        
        # Check validators that would be affected
        # Validators with allow_override=True are affected
        for validator_id, config in self.policy.validators.items():
            if config.allow_override:
                self.affected_validators.add(validator_id)
        
        # Note: Actual impact depends on decisions made at runtime
        # This is a static assessment based on policy configuration
    
    def record_downgrade(
        self,
        validator_id: str,
        decision_code: str,
        original_outcome: DecisionOutcome,
        final_outcome: DecisionOutcome,
        reason: str = "breakglass_override",
    ) -> None:
        """
        Record a decision downgrade due to breakglass
        
        Args:
            validator_id: Validator ID
            decision_code: Decision code
            original_outcome: Original decision outcome (before breakglass)
            final_outcome: Final decision outcome (after breakglass)
            reason: Reason for downgrade
        """
        if original_outcome == DecisionOutcome.BLOCK and final_outcome != DecisionOutcome.BLOCK:
            self.affected_validators.add(validator_id)
            self.downgraded_decisions.append({
                "validator_id": validator_id,
                "decision_code": decision_code,
                "original_outcome": original_outcome.value,
                "final_outcome": final_outcome.value,
                "reason": reason,
            })
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get impact summary
        
        Returns:
            Dict with impact summary
        """
        return {
            "breakglass_active": self.policy.global_override.enabled if self.policy.global_override else False,
            "affected_validators": sorted(list(self.affected_validators)),
            "affected_validator_count": len(self.affected_validators),
            "downgraded_decision_count": len(self.downgraded_decisions),
            "downgraded_decisions": self.downgraded_decisions,
        }
    
    def get_explain_text(self) -> str:
        """
        Get human-readable impact explanation
        
        Returns:
            Multi-line explanation string
        """
        if not self.policy.global_override or not self.policy.global_override.enabled:
            return ""
        
        lines = []
        lines.append("[BREAKGLASS ACTIVE] Emergency override is enabled")
        
        if self.policy.global_override.expires_at:
            lines.append(f"  Expires: {self.policy.global_override.expires_at}")
        
        if self.affected_validators:
            lines.append(f"  Affected Validators ({len(self.affected_validators)}): {', '.join(sorted(self.affected_validators))}")
        
        if self.downgraded_decisions:
            block_count = sum(1 for d in self.downgraded_decisions if d["original_outcome"] == "block")
            if block_count > 0:
                lines.append(f"  Impact: {block_count} BLOCK decision(s) downgraded to {self.downgraded_decisions[0]['final_outcome'].upper()}")
        
        return "\n".join(lines)


def assess_breakglass_impact(
    policy: Policy,
    decisions: Optional[List[Decision]] = None,
) -> BreakglassImpact:
    """
    Assess breakglass impact on policy and decisions
    
    Args:
        policy: Policy with breakglass override
        decisions: Optional list of decisions to analyze
        
    Returns:
        BreakglassImpact object
    """
    impact = BreakglassImpact(policy)
    
    # If decisions provided, analyze actual impact
    if decisions:
        for decision in decisions:
            # Check if decision was affected by breakglass
            evidence = decision.evidence or {}
            if "breakglass_override" in evidence or "override_applied" in evidence:
                impact.record_downgrade(
                    validator_id=decision.validator_id,
                    decision_code=decision.code,
                    original_outcome=DecisionOutcome.BLOCK,  # Assume BLOCK originally
                    final_outcome=decision.decision,
                    reason="breakglass_override",
                )
    
    return impact


__all__ = [
    "BreakglassImpact",
    "assess_breakglass_impact",
]
