# failcore/core/validate/explain.py
"""
Explain: Human-readable decision explanation generator.

This module provides utilities to aggregate and explain validation decisions.

Design principles:
- Make "why was this blocked" a first-class capability
- Aggregate decisions by validator/rule/code
- Generate human-readable summaries
- Provide remediation suggestions
- Support CLI, UI, and programmatic access
- Show which validators would trigger, evidence for each rule, and final enforcement mode
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from collections import defaultdict

from .contracts import Decision, DecisionOutcome, RiskLevel, Policy, EnforcementMode
from .audit import get_audit_logger
from .breakglass import assess_breakglass_impact


class DecisionExplanation:
    """
    Aggregated explanation of validation decisions.
    
    Contains:
    - Summary of all decisions
    - Grouped by validator/rule/code
    - Remediation suggestions
    - Current enforcement mode
    - Validator trigger information
    - Rule evidence details
    - Final enforcement after policy merge
    """
    
    def __init__(
        self,
        decisions: List[Decision],
        policy: Optional[Policy] = None,
        triggered_validators: Optional[List[str]] = None,
    ):
        """
        Initialize explanation
        
        Args:
            decisions: List of validation decisions
            policy: Policy used (for enforcement mode info)
            triggered_validators: List of validator IDs that were triggered
        """
        self.decisions = decisions
        self.policy = policy
        self.triggered_validators = triggered_validators or []
        self._analyze()
    
    def _analyze(self) -> None:
        """Analyze decisions and build aggregated data"""
        self.total = len(self.decisions)
        self.by_outcome: Dict[DecisionOutcome, List[Decision]] = defaultdict(list)
        self.by_validator: Dict[str, List[Decision]] = defaultdict(list)
        self.by_risk: Dict[RiskLevel, List[Decision]] = defaultdict(list)
        self.by_code: Dict[str, List[Decision]] = defaultdict(list)
        
        for decision in self.decisions:
            self.by_outcome[decision.decision].append(decision)
            self.by_validator[decision.validator_id].append(decision)
            self.by_risk[decision.risk_level].append(decision)
            self.by_code[decision.code].append(decision)
    
    @property
    def blocked(self) -> List[Decision]:
        """Get all blocking decisions"""
        return self.by_outcome.get(DecisionOutcome.BLOCK, [])
    
    @property
    def warnings(self) -> List[Decision]:
        """Get all warning decisions"""
        return self.by_outcome.get(DecisionOutcome.WARN, [])
    
    @property
    def allowed(self) -> List[Decision]:
        """Get all allow decisions"""
        return self.by_outcome.get(DecisionOutcome.ALLOW, [])
    
    @property
    def is_blocked(self) -> bool:
        """Whether any decision blocks execution"""
        return len(self.blocked) > 0
    
    @property
    def critical_decisions(self) -> List[Decision]:
        """Get critical risk decisions"""
        return self.by_risk.get(RiskLevel.CRITICAL, [])
    
    @property
    def enforcement_mode(self) -> Optional[EnforcementMode]:
        """Get effective enforcement mode from policy"""
        if not self.policy:
            return None
        
        # Check if breakglass override is active
        if self.policy.global_override and self.policy.global_override.enabled:
            # Check expiration
            if self.policy.global_override.expires_at:
                from datetime import datetime, timezone
                try:
                    expires = datetime.fromisoformat(self.policy.global_override.expires_at)
                    if expires > datetime.now(timezone.utc):
                        return EnforcementMode.BLOCK  # Breakglass active
                except Exception:
                    pass
        
        # Check validator-specific enforcement
        # Return the most restrictive enforcement mode among triggered validators
        enforcement_modes = []
        for validator_id in self.triggered_validators:
            if validator_id in self.policy.validators:
                config = self.policy.validators[validator_id]
                if config.enforcement:
                    enforcement_modes.append(config.enforcement)
        
        if not enforcement_modes:
            return None
        
        # Return most restrictive: BLOCK > WARN > SHADOW
        if EnforcementMode.BLOCK in enforcement_modes:
            return EnforcementMode.BLOCK
        elif EnforcementMode.WARN in enforcement_modes:
            return EnforcementMode.WARN
        elif EnforcementMode.SHADOW in enforcement_modes:
            return EnforcementMode.SHADOW
        
        return enforcement_modes[0]  # Fallback
    
    def get_validator_details(self) -> Dict[str, Any]:
        """
        Get detailed information about triggered validators
        
        Returns:
            Dict mapping validator_id -> details
        """
        details = {}
        
        for validator_id in self.triggered_validators:
            validator_decisions = self.by_validator.get(validator_id, [])
            
            # Get policy config for this validator
            config = None
            if self.policy and validator_id in self.policy.validators:
                config = self.policy.validators[validator_id]
            
            details[validator_id] = {
                "triggered": True,
                "decision_count": len(validator_decisions),
                "enforcement": config.enforcement.value if config and config.enforcement else None,
                "enabled": config.enabled if config else True,
                "decisions": [
                    {
                        "code": d.code,
                        "outcome": d.decision.value,
                        "message": d.message,
                        "risk_level": d.risk_level.value,
                        "rule_id": d.rule_id,
                        "evidence": d.evidence,
                    }
                    for d in validator_decisions
                ],
            }
        
        return details
    
    def get_rule_evidence(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get evidence for each rule that was triggered
        
        Returns:
            Dict mapping rule_id -> list of evidence dicts
        """
        rule_evidence = defaultdict(list)
        
        for decision in self.decisions:
            if decision.rule_id:
                rule_evidence[decision.rule_id].append({
                    "code": decision.code,
                    "validator": decision.validator_id,
                    "evidence": decision.evidence,
                    "outcome": decision.decision.value,
                    "risk_level": decision.risk_level.value,
                })
        
        return dict(rule_evidence)
    
    def get_summary(self, verbose: bool = False) -> str:
        """
        Generate human-readable summary.
        
        Args:
            verbose: If True, include detailed evidence and all decisions
        
        Returns:
            Multi-line summary string (hierarchical: Summary -> Details -> Evidence)
        """
        if not verbose:
            return self._get_summary_concise()
        
        return self._get_summary_verbose()
    
    def _get_summary_concise(self) -> str:
        """Generate concise summary (default)"""
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("Validation Summary")
        lines.append("=" * 60)
        
        # Enforcement mode
        if self.enforcement_mode:
            lines.append(f"Effective Enforcement: {self.enforcement_mode.value.upper()}")
            lines.append("")
        
        # Outcome summary
        blocked_count = len(self.blocked)
        warning_count = len(self.warnings)
        
        if blocked_count > 0:
            lines.append(f"[BLOCK] Validation blocked: {blocked_count} blocking decision(s)")
        elif warning_count > 0:
            lines.append(f"[WARN] Validation passed with {warning_count} warning(s)")
        else:
            lines.append("[OK] Validation passed")
        lines.append("")
        
        # Top 3 blocking reasons (filter low-confidence taint flows)
        if self.blocked:
            lines.append("Top Reasons:")
            shown_count = 0
            for decision in self.blocked:
                # Skip low-confidence taint flows in concise view
                if decision.validator_id == "taint_flow":
                    evidence = decision.evidence or {}
                    binding_confidence = evidence.get("binding_confidence", "unknown")
                    if binding_confidence == "low":
                        continue  # Skip low-confidence flows in concise view
                
                shown_count += 1
                if shown_count > 3:
                    break
                
                lines.append(f"  {shown_count}. {decision.message} ({decision.code})")
                if decision.rule_id:
                    lines.append(f"     Rule: {decision.rule_id}")
                
                # Show confidence for taint flows
                if decision.validator_id == "taint_flow":
                    evidence = decision.evidence or {}
                    binding_confidence = evidence.get("binding_confidence", "unknown")
                    if binding_confidence != "high":
                        lines.append(f"     Confidence: {binding_confidence}")
            
            if len(self.blocked) > shown_count:
                lines.append(f"  ... and {len(self.blocked) - shown_count} more (use --verbose for all)")
            lines.append("")
        
        # Triggered validators (summary)
        if self.triggered_validators:
            lines.append(f"Triggered Validators: {', '.join(self.triggered_validators)}")
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("Use --verbose for full details")
        
        return "\n".join(lines)
    
    def _get_summary_verbose(self) -> str:
        """Generate verbose summary with all details"""
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("Validation Summary (Verbose)")
        lines.append("=" * 60)
        
        # Enforcement mode
        if self.enforcement_mode:
            lines.append(f"Effective Enforcement: {self.enforcement_mode.value.upper()}")
            lines.append("")
        
        # Outcome summary
        blocked_count = len(self.blocked)
        warning_count = len(self.warnings)
        allowed_count = len(self.allowed)
        
        lines.append(f"Total decisions: {self.total}")
        lines.append(f"  - Blocked: {blocked_count}")
        lines.append(f"  - Warnings: {warning_count}")
        lines.append(f"  - Allowed: {allowed_count}")
        lines.append("")
        
        # Triggered validators
        if self.triggered_validators:
            lines.append("Triggered Validators:")
            for validator_id in self.triggered_validators:
                count = len(self.by_validator.get(validator_id, []))
                lines.append(f"  - {validator_id}: {count} decision(s)")
            lines.append("")
        
        # Risk summary
        if self.by_risk:
            lines.append("Risk breakdown:")
            for risk in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]:
                count = len(self.by_risk.get(risk, []))
                if count > 0:
                    lines.append(f"  - {risk.value.upper()}: {count}")
            lines.append("")
        
        # Blocking decisions (detailed)
        if self.blocked:
            lines.append("BLOCKING DECISIONS:")
            lines.append("-" * 60)
            for i, decision in enumerate(self.blocked, 1):
                lines.append(f"\n{i}. {decision.message}")
                lines.append(f"   Code: {decision.code}")
                lines.append(f"   Validator: {decision.validator_id}")
                if decision.rule_id:
                    lines.append(f"   Rule: {decision.rule_id}")
                lines.append(f"   Risk: {decision.risk_level.value.upper()}")
                
                # Evidence (full)
                if decision.evidence:
                    lines.append("   Evidence:")
                    for key, value in decision.evidence.items():
                        value_str = str(value)
                        if len(value_str) > 200:
                            value_str = value_str[:200] + "..."
                        lines.append(f"     - {key}: {value_str}")
                
                # Remediation
                if decision.remediation:
                    lines.append(f"   Remediation: {decision.remediation}")
                
                # Override info
                if decision.overrideable:
                    lines.append("   [WARNING] This decision can be overridden")
            lines.append("")
        
        # Warnings (summary)
        if self.warnings:
            lines.append("WARNINGS:")
            lines.append("-" * 60)
            for decision in self.warnings:
                lines.append(f"  [WARN] {decision.message} ({decision.code})")
                if decision.rule_id:
                    lines.append(f"    Rule: {decision.rule_id}")
            lines.append("")
        
        # Validator summary
        if len(self.by_validator) > 1:
            lines.append("By Validator:")
            for validator_id, validator_decisions in self.by_validator.items():
                blocked = sum(1 for d in validator_decisions if d.is_blocking)
                warned = sum(1 for d in validator_decisions if d.is_warning)
                lines.append(f"  - {validator_id}: {len(validator_decisions)} decisions "
                           f"({blocked} blocked, {warned} warned)")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def get_short_summary(self) -> str:
        """
        Generate short one-line summary.
        
        Returns:
            Single-line summary string
        """
        blocked_count = len(self.blocked)
        warning_count = len(self.warnings)
        
        if blocked_count > 0:
            return f"[BLOCK] Validation blocked: {blocked_count} blocking decision(s), {warning_count} warning(s)"
        elif warning_count > 0:
            return f"[WARN] Validation passed with {warning_count} warning(s)"
        else:
            return "[OK] Validation passed"
    
    def get_remediation_steps(self) -> List[str]:
        """
        Get list of remediation steps.
        
        Returns:
            List of remediation suggestions
        """
        steps = []
        
        for decision in self.blocked:
            if decision.remediation:
                steps.append(f"[{decision.code}] {decision.remediation}")
        
        if not steps:
            steps.append("No specific remediation steps available. "
                        "Review the blocking decisions above.")
        
        return steps
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            "total": self.total,
            "blocked": len(self.blocked),
            "warnings": len(self.warnings),
            "allowed": len(self.allowed),
            "is_blocked": self.is_blocked,
            "enforcement_mode": self.enforcement_mode.value if self.enforcement_mode else None,
            "triggered_validators": self.triggered_validators,
            "validator_details": self.get_validator_details(),
            "rule_evidence": self.get_rule_evidence(),
            "summary": self.get_short_summary(),
            "decisions": [
                {
                    "code": d.code,
                    "decision": d.decision.value,
                    "validator_id": d.validator_id,
                    "rule_id": d.rule_id,
                    "message": d.message,
                    "risk_level": d.risk_level.value,
                    "evidence": d.evidence,
                }
                for d in self.decisions
            ],
            "remediation": self.get_remediation_steps(),
        }


def explain_decisions(
    decisions: List[Decision],
    policy: Optional[Policy] = None,
    triggered_validators: Optional[List[str]] = None,
) -> DecisionExplanation:
    """
    Create explanation from decisions.
    
    Args:
        decisions: List of validation decisions
        policy: Policy used (for enforcement mode info)
        triggered_validators: List of validator IDs that were triggered
    
    Returns:
        DecisionExplanation with aggregated information
    """
    return DecisionExplanation(decisions, policy, triggered_validators)


def print_explanation(decisions: List[Decision], policy: Optional[Policy] = None) -> None:
    """
    Print human-readable explanation to stdout.
    
    Args:
        decisions: List of validation decisions
        policy: Policy used (for enforcement mode info)
    """
    explanation = explain_decisions(decisions, policy)
    print(explanation.get_summary())


__all__ = [
    "DecisionExplanation",
    "explain_decisions",
    "print_explanation",
]
