"""
Semantic Guard - Detectors

Detect malicious patterns using semantic rules
"""

from typing import Dict, Any, List
from failcore.core.rules.semantic import SemanticRule, RuleRegistry, RuleSeverity
from .verdict import SemanticVerdict, VerdictAction


class SemanticDetector:
    """
    Semantic pattern detector
    
    Evaluates tool calls against semantic rules
    """
    
    def __init__(
        self,
        registry: RuleRegistry = None,
        min_severity: RuleSeverity = RuleSeverity.HIGH,
        enabled_categories: List[str] = None,
    ):
        """
        Args:
            registry: Rule registry
            min_severity: Minimum severity to enforce
            enabled_categories: List of enabled categories (None = all)
        """
        self.registry = registry or RuleRegistry()
        self.min_severity = min_severity
        self.enabled_categories = enabled_categories
        
        # Statistics
        self.total_checks = 0
        self.violations_found = 0
    
    def check(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> SemanticVerdict:
        """
        Check tool call against semantic rules
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            context: Execution context
        
        Returns:
            Semantic verdict
        """
        self.total_checks += 1
        
        # Get applicable rules
        rules = self._get_applicable_rules()
        
        # Check all rules
        violations = []
        for rule in rules:
            if rule.check(tool_name, params):
                violations.append(rule)
        
        # Determine action
        if violations:
            self.violations_found += 1
            action = self._determine_action(violations)
        else:
            action = VerdictAction.ALLOW
        
        # Create verdict
        verdict = SemanticVerdict(
            action=action,
            violations=violations,
            tool_name=tool_name,
            params=params,
            context=context or {},
        )
        
        return verdict
    
    def _get_applicable_rules(self) -> List[SemanticRule]:
        """Get rules to check"""
        # Start with minimum severity
        rules = self.registry.get_by_severity(self.min_severity)
        
        # Filter by enabled categories
        if self.enabled_categories is not None:
            rules = [r for r in rules if r.category.value in self.enabled_categories]
        
        return rules
    
    def _determine_action(self, violations: List[SemanticRule]) -> VerdictAction:
        """Determine action based on violations"""
        # Get max severity
        max_severity = max(v.severity for v in violations)
        
        # Map severity to action
        if max_severity == RuleSeverity.CRITICAL:
            return VerdictAction.BLOCK
        elif max_severity == RuleSeverity.HIGH:
            return VerdictAction.BLOCK
        elif max_severity == RuleSeverity.MEDIUM:
            return VerdictAction.WARN
        else:
            return VerdictAction.LOG
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            "total_checks": self.total_checks,
            "violations_found": self.violations_found,
            "violation_rate": self.violations_found / self.total_checks if self.total_checks > 0 else 0.0,
        }


__all__ = ["SemanticDetector"]
