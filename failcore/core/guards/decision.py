#failcore/core/guards/descision.py
"""
Guard Decision Conversion

Unified conversion functions to convert guard-specific verdicts/decisions
to the standard DecisionV1 format used by the validation system.

This module provides a bridge between guard-specific decision structures
(DLPAction, VerdictAction, etc.) and the unified DecisionV1 format.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from enum import Enum

from failcore.core.validate.contracts import Decision, DecisionOutcome, RiskLevel
from .dlp.policies import DLPAction, DLPPolicy
from .semantic.verdict import VerdictAction, SemanticVerdict
from .taint.tag import TaintTag, DataSensitivity


def dlp_action_to_decision_outcome(action: DLPAction) -> DecisionOutcome:
    """
    Convert DLP action to decision outcome.
    
    Mapping:
    - ALLOW -> ALLOW
    - WARN -> WARN
    - WARN_APPROVAL_NEEDED -> WARN (with requires_approval=True)
    - SANITIZE -> WARN (sanitization is a warning, not blocking)
    - BLOCK -> BLOCK
    
    Args:
        action: DLP action
        
    Returns:
        Decision outcome
    """
    mapping = {
        DLPAction.ALLOW: DecisionOutcome.ALLOW,
        DLPAction.WARN: DecisionOutcome.WARN,
        DLPAction.WARN_APPROVAL_NEEDED: DecisionOutcome.WARN,
        DLPAction.SANITIZE: DecisionOutcome.WARN,
        DLPAction.BLOCK: DecisionOutcome.BLOCK,
    }
    return mapping.get(action, DecisionOutcome.WARN)


def verdict_action_to_decision_outcome(action: VerdictAction) -> DecisionOutcome:
    """
    Convert verdict action to decision outcome.
    
    Mapping:
    - ALLOW -> ALLOW
    - WARN -> WARN
    - LOG -> ALLOW (logging doesn't block)
    - BLOCK -> BLOCK
    
    Args:
        action: Verdict action
        
    Returns:
        Decision outcome
    """
    mapping = {
        VerdictAction.ALLOW: DecisionOutcome.ALLOW,
        VerdictAction.WARN: DecisionOutcome.WARN,
        VerdictAction.LOG: DecisionOutcome.ALLOW,
        VerdictAction.BLOCK: DecisionOutcome.BLOCK,
    }
    return mapping.get(action, DecisionOutcome.ALLOW)


def data_sensitivity_to_risk_level(sensitivity: DataSensitivity) -> RiskLevel:
    """
    Convert data sensitivity to risk level.
    
    Mapping:
    - PUBLIC -> LOW
    - INTERNAL -> LOW
    - CONFIDENTIAL -> MEDIUM
    - PII -> HIGH
    - SECRET -> CRITICAL
    
    Args:
        sensitivity: Data sensitivity level
        
    Returns:
        Risk level
    """
    mapping = {
        DataSensitivity.PUBLIC: RiskLevel.LOW,
        DataSensitivity.INTERNAL: RiskLevel.LOW,
        DataSensitivity.CONFIDENTIAL: RiskLevel.MEDIUM,
        DataSensitivity.PII: RiskLevel.HIGH,
        DataSensitivity.SECRET: RiskLevel.CRITICAL,
    }
    return mapping.get(sensitivity, RiskLevel.MEDIUM)


def dlp_policy_to_decision(
    policy: DLPPolicy,
    validator_id: str,
    code: str,
    message: str,
    evidence: Optional[Dict[str, Any]] = None,
    pattern_id: Optional[str] = None,
    sensitivity: Optional[DataSensitivity] = None,
) -> Decision:
    """
    Convert DLP policy decision to DecisionV1.
    
    Args:
        policy: DLP policy
        validator_id: Validator ID (e.g., "dlp_guard")
        code: Decision code (e.g., "FC_DLP_PII_DETECTED")
        message: Human-readable message
        evidence: Additional evidence
        pattern_id: Pattern ID that triggered this decision
        sensitivity: Data sensitivity level
        
    Returns:
        DecisionV1 object
    """
    decision_outcome = dlp_action_to_decision_outcome(policy.action)
    risk_level = data_sensitivity_to_risk_level(sensitivity) if sensitivity else RiskLevel.MEDIUM
    
    # Build evidence
    decision_evidence = evidence or {}
    decision_evidence.update({
        "dlp_action": policy.action.value,
        "dlp_reason": policy.reason,
        "auto_sanitize": policy.auto_sanitize,
        "notify": policy.notify,
    })
    if pattern_id:
        decision_evidence["pattern_id"] = pattern_id
    if sensitivity:
        decision_evidence["sensitivity"] = sensitivity.value
        decision_evidence["risk_level_source"] = "data_sensitivity"
    
    # Determine if requires approval
    requires_approval = policy.action == DLPAction.WARN_APPROVAL_NEEDED
    
    # Create decision
    if decision_outcome == DecisionOutcome.BLOCK:
        return Decision.block(
            code=code,
            validator_id=validator_id,
            message=message,
            evidence=decision_evidence,
            risk_level=risk_level,
            rule_id=pattern_id,
            requires_approval=requires_approval,
            remediation=policy.reason or "Review DLP policy configuration",
        )
    elif decision_outcome == DecisionOutcome.WARN:
        return Decision.warn(
            code=code,
            validator_id=validator_id,
            message=message,
            evidence=decision_evidence,
            risk_level=risk_level,
            rule_id=pattern_id,
            requires_approval=requires_approval,
            remediation=policy.reason or "Review DLP policy configuration",
        )
    else:
        return Decision.allow(
            code=code,
            validator_id=validator_id,
            message=message,
            evidence=decision_evidence,
            risk_level=risk_level,
            rule_id=pattern_id,
        )


def semantic_verdict_to_decision(
    verdict: SemanticVerdict,
    validator_id: str,
) -> List[Decision]:
    """
    Convert semantic verdict to list of DecisionV1 objects.
    
    Creates one Decision per violated rule, or a single ALLOW decision
    if no violations.
    
    Args:
        verdict: Semantic verdict
        validator_id: Validator ID (e.g., "semantic_intent")
        
    Returns:
        List of DecisionV1 objects
    """
    decisions: List[Decision] = []
    
    if not verdict.has_violations:
        # No violations: single ALLOW decision
        decisions.append(
            Decision.allow(
                code="FC_SEMANTIC_CLEAN",
                validator_id=validator_id,
                message=f"No semantic violations detected for {verdict.tool_name}",
                evidence={
                    "tool_name": verdict.tool_name,
                    "timestamp": verdict.timestamp,
                },
            )
        )
        return decisions
    
    # Map verdict action to decision outcome
    decision_outcome = verdict_action_to_decision_outcome(verdict.action)
    
    # Create one decision per violated rule
    for rule in verdict.violations:
        # Map rule severity to risk level
        severity_map = {
            "critical": RiskLevel.CRITICAL,
            "high": RiskLevel.HIGH,
            "medium": RiskLevel.MEDIUM,
            "low": RiskLevel.LOW,
        }
        risk_level = severity_map.get(rule.severity.value.lower(), RiskLevel.MEDIUM)
        
        # Build evidence
        evidence = {
            "tool_name": verdict.tool_name,
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "rule_category": rule.category.value,
            "rule_severity": rule.severity.value,
            "rule_description": rule.description,
            "violation_count": len(verdict.violations),
            "timestamp": verdict.timestamp,
        }
        
        # Create decision
        code = f"FC_SEMANTIC_{rule.rule_id}"
        message = f"Semantic violation: {rule.name} - {rule.description}"
        
        if decision_outcome == DecisionOutcome.BLOCK:
            decisions.append(
                Decision.block(
                    code=code,
                    validator_id=validator_id,
                    message=message,
                    evidence=evidence,
                    risk_level=risk_level,
                    rule_id=rule.rule_id,
                    remediation=f"Review rule: {rule.name}. Examples: {', '.join(rule.examples[:2])}",
                )
            )
        elif decision_outcome == DecisionOutcome.WARN:
            decisions.append(
                Decision.warn(
                    code=code,
                    validator_id=validator_id,
                    message=message,
                    evidence=evidence,
                    risk_level=risk_level,
                    rule_id=rule.rule_id,
                    remediation=f"Review rule: {rule.name}. Examples: {', '.join(rule.examples[:2])}",
                )
            )
        else:
            decisions.append(
                Decision.allow(
                    code=code,
                    validator_id=validator_id,
                    message=message,
                    evidence=evidence,
                    risk_level=risk_level,
                    rule_id=rule.rule_id,
                )
            )
    
    return decisions


__all__ = [
    "dlp_action_to_decision_outcome",
    "verdict_action_to_decision_outcome",
    "data_sensitivity_to_risk_level",
    "dlp_policy_to_decision",
    "semantic_verdict_to_decision",
]
