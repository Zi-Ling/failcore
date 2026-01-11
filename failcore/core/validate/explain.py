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
"""

from __future__ import annotations

from typing import Dict, List, Optional
from collections import defaultdict

from .contracts import Decision, DecisionOutcome, RiskLevel


class DecisionExplanation:
    """
    Aggregated explanation of validation decisions.
    
    Contains:
    - Summary of all decisions
    - Grouped by validator/rule/code
    - Remediation suggestions
    - Current enforcement mode
    """
    
    def __init__(self, decisions: List[Decision]):
        self.decisions = decisions
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
    
    def get_summary(self) -> str:
        """
        Generate human-readable summary.
        
        Returns:
            Multi-line summary string
        """
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("Validation Summary")
        lines.append("=" * 60)
        
        # Outcome summary
        blocked_count = len(self.blocked)
        warning_count = len(self.warnings)
        allowed_count = len(self.allowed)
        
        lines.append(f"Total decisions: {self.total}")
        lines.append(f"  - Blocked: {blocked_count}")
        lines.append(f"  - Warnings: {warning_count}")
        lines.append(f"  - Allowed: {allowed_count}")
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
                
                # Evidence
                if decision.evidence:
                    lines.append("   Evidence:")
                    for key, value in decision.evidence.items():
                        lines.append(f"     - {key}: {value}")
                
                # Remediation
                if decision.remediation:
                    lines.append(f"   Remediation: {decision.remediation}")
                
                # Override info
                if decision.overrideable:
                    lines.append("   ⚠️  This decision can be overridden")
            lines.append("")
        
        # Warnings (summary)
        if self.warnings:
            lines.append("WARNINGS:")
            lines.append("-" * 60)
            for decision in self.warnings:
                lines.append(f"  ⚠️  {decision.message} ({decision.code})")
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
            return f"❌ Validation blocked: {blocked_count} blocking decision(s), {warning_count} warning(s)"
        elif warning_count > 0:
            return f"⚠️  Validation passed with {warning_count} warning(s)"
        else:
            return "✅ Validation passed"
    
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
            "summary": self.get_short_summary(),
            "decisions": [
                {
                    "code": d.code,
                    "decision": d.decision.value,
                    "validator_id": d.validator_id,
                    "message": d.message,
                    "risk_level": d.risk_level.value,
                }
                for d in self.decisions
            ],
            "remediation": self.get_remediation_steps(),
        }


def explain_decisions(decisions: List[Decision]) -> DecisionExplanation:
    """
    Create explanation from decisions.
    
    Args:
        decisions: List of validation decisions
    
    Returns:
        DecisionExplanation with aggregated information
    """
    return DecisionExplanation(decisions)


def print_explanation(decisions: List[Decision]) -> None:
    """
    Print human-readable explanation to stdout.
    
    Args:
        decisions: List of validation decisions
    """
    explanation = explain_decisions(decisions)
    print(explanation.get_summary())


__all__ = [
    "DecisionExplanation",
    "explain_decisions",
    "print_explanation",
]
