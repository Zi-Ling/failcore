# failcore/core/rules/engine.py
"""
Rule Execution Engine

Provides unified rule execution logic across all guard modules
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .models import Rule, RuleAction, RuleSeverity, RuleCategory
from .registry import RuleRegistry


@dataclass
class RuleMatch:
    """
    Rule match result
    """
    rule: Rule
    matched: bool
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class RuleEngineResult:
    """
    Rule engine evaluation result
    """
    action: RuleAction
    matches: List[RuleMatch]
    highest_severity: Optional[RuleSeverity] = None
    confidence: float = 1.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_blocked(self) -> bool:
        """Check if action is BLOCK"""
        return self.action == RuleAction.BLOCK
    
    @property
    def is_warned(self) -> bool:
        """Check if action is WARN"""
        return self.action == RuleAction.WARN
    
    @property
    def is_allowed(self) -> bool:
        """Check if action is ALLOW"""
        return self.action == RuleAction.ALLOW


class RuleEngine:
    """
    Rule execution engine
    
    Evaluates tool calls against registered rules and determines actions
    """
    
    def __init__(
        self,
        registry: RuleRegistry,
        default_action: RuleAction = RuleAction.ALLOW,
        fail_open: bool = True,
    ):
        """
        Initialize rule engine
        
        Args:
            registry: RuleRegistry to use
            default_action: Default action when no rules match
            fail_open: If True, allow on internal errors (graceful degradation)
        """
        self.registry = registry
        self.default_action = default_action
        self.fail_open = fail_open
    
    def evaluate(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        categories: Optional[List[RuleCategory]] = None,
        min_severity: Optional[RuleSeverity] = None,
    ) -> RuleEngineResult:
        """
        Evaluate tool call against rules
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            context: Optional context
            categories: Optional list of categories to check (None = all)
            min_severity: Optional minimum severity to enforce
        
        Returns:
            RuleEngineResult with action and matches
        """
        try:
            # Get applicable rules
            rules = self._get_applicable_rules(categories, min_severity)
            
            # Evaluate each rule
            matches = []
            for rule in rules:
                if rule.check(tool_name, params, context):
                    match = RuleMatch(
                        rule=rule,
                        matched=True,
                        confidence=1.0 - rule.false_positive_rate,
                        evidence={"tool": tool_name, "params": params},
                        reason=rule.description,
                    )
                    matches.append(match)
            
            # Determine action
            if not matches:
                return RuleEngineResult(
                    action=self.default_action,
                    matches=[],
                    reason="No rules matched",
                )
            
            # Get highest severity match
            highest_severity = max(match.rule.severity for match in matches)
            
            # Determine action based on highest severity
            action = self._severity_to_action(highest_severity)
            
            # Override with rule-specific action if any match has explicit action
            for match in matches:
                if match.rule.action != RuleAction.WARN:  # WARN is default
                    action = match.rule.action
                    break
            
            # Build reason
            rule_names = [m.rule.name for m in matches]
            reason = f"Matched {len(matches)} rule(s): {', '.join(rule_names)}"
            
            return RuleEngineResult(
                action=action,
                matches=matches,
                highest_severity=highest_severity,
                confidence=min(m.confidence for m in matches),
                reason=reason,
                metadata={
                    "matched_rule_ids": [m.rule.rule_id for m in matches],
                    "matched_categories": list(set(m.rule.category.value for m in matches)),
                },
            )
        
        except Exception as e:
            # Fail open on internal errors
            if self.fail_open:
                return RuleEngineResult(
                    action=RuleAction.ALLOW,
                    matches=[],
                    reason=f"Engine error (fail-open): {str(e)}",
                    metadata={"error": str(e)},
                )
            else:
                raise
    
    def _get_applicable_rules(
        self,
        categories: Optional[List[RuleCategory]],
        min_severity: Optional[RuleSeverity],
    ) -> List[Rule]:
        """Get applicable rules based on filters"""
        if categories:
            # Get rules for specific categories
            rules = []
            for category in categories:
                rules.extend(self.registry.get_rules_by_category(category))
        elif min_severity:
            # Get rules by severity
            rules = self.registry.get_rules_by_severity(min_severity)
        else:
            # Get all rules
            rules = self.registry.get_all_rules()
        
        return rules
    
    def _severity_to_action(self, severity: RuleSeverity) -> RuleAction:
        """Map severity to default action"""
        mapping = {
            RuleSeverity.CRITICAL: RuleAction.BLOCK,
            RuleSeverity.HIGH: RuleAction.BLOCK,
            RuleSeverity.MEDIUM: RuleAction.WARN,
            RuleSeverity.LOW: RuleAction.LOG,
        }
        return mapping.get(severity, RuleAction.WARN)


__all__ = [
    "RuleMatch",
    "RuleEngineResult",
    "RuleEngine",
]
