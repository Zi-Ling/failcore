"""
Semantic Guard - Detectors

Detect malicious patterns using semantic rules
"""

from typing import Dict, Any, List, Optional
from failcore.core.rules import RuleRegistry, RuleEngine, RuleCategory, RuleSeverity, RuleAction
from .verdict import SemanticVerdict, VerdictAction


class SemanticDetector:
    """
    Semantic pattern detector
    
    Evaluates tool calls against semantic rules using unified rule system
    """
    
    def __init__(
        self,
        rule_registry: Optional[RuleRegistry] = None,
        min_severity: RuleSeverity = RuleSeverity.HIGH,
        enabled_categories: Optional[List[str]] = None,
    ):
        """
        Args:
            rule_registry: Rule registry (will load semantic ruleset if not provided)
            min_severity: Minimum severity to enforce
            enabled_categories: List of enabled categories (None = all)
        """
        if rule_registry is None:
            rule_registry = _get_default_semantic_registry()
        
        self.rule_registry = rule_registry
        self.rule_engine = RuleEngine(rule_registry, default_action=RuleAction.ALLOW)
        self.min_severity = min_severity
        self.enabled_categories = enabled_categories
        
        # Statistics
        self.total_checks = 0
        self.violations_found = 0
    
    def check(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
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
        
        # Determine categories to check
        categories = None
        if self.enabled_categories:
            # Map category strings to RuleCategory enum
            category_map = {
                "semantic.secret_leakage": RuleCategory.SEMANTIC_SECRET_LEAKAGE,
                "semantic.injection": RuleCategory.SEMANTIC_INJECTION,
                "semantic.dangerous_combo": RuleCategory.SEMANTIC_DANGEROUS_COMBO,
                "semantic.path_traversal": RuleCategory.SEMANTIC_PATH_TRAVERSAL,
            }
            categories = [category_map.get(c) for c in self.enabled_categories if c in category_map]
        
        # Use rule engine to evaluate
        result = self.rule_engine.evaluate(
            tool_name=tool_name,
            params=params,
            context=context,
            categories=categories,
            min_severity=self.min_severity,
        )
        
        # Convert rule matches to violations
        violations = []
        for match in result.matches:
            violations.append(match.rule)
        
        # Determine action
        if violations:
            self.violations_found += 1
            action = self._determine_action(violations)
        else:
            action = VerdictAction.ALLOW
        
        # Map RuleAction to VerdictAction
        action_map = {
            RuleAction.BLOCK: VerdictAction.BLOCK,
            RuleAction.WARN: VerdictAction.WARN,
            RuleAction.LOG: VerdictAction.LOG,
            RuleAction.ALLOW: VerdictAction.ALLOW,
        }
        verdict_action = action_map.get(result.action, VerdictAction.WARN)
        
        # Create verdict
        verdict = SemanticVerdict(
            action=verdict_action,
            violations=violations,
            tool_name=tool_name,
            params=params,
            context=context or {},
        )
        
        return verdict
    
    def _determine_action(self, violations: List) -> VerdictAction:
        """Determine action based on violations"""
        # Get max severity
        severity_map = {
            RuleSeverity.CRITICAL: 4,
            RuleSeverity.HIGH: 3,
            RuleSeverity.MEDIUM: 2,
            RuleSeverity.LOW: 1,
        }
        
        max_severity_level = max(
            severity_map.get(v.severity, 1) for v in violations
        )
        
        if max_severity_level >= 4:  # CRITICAL
            return VerdictAction.BLOCK
        elif max_severity_level >= 3:  # HIGH
            return VerdictAction.BLOCK
        elif max_severity_level >= 2:  # MEDIUM
            return VerdictAction.WARN
        else:  # LOW
            return VerdictAction.LOG


def _get_default_semantic_registry() -> RuleRegistry:
    """Get default semantic rule registry with ruleset loaded"""
    from failcore.infra.rulesets import FileSystemLoader
    from failcore.core.rules.loader import CompositeLoader
    from pathlib import Path
    
    # Try to load from default rulesets
    default_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "rulesets" / "default"
    
    loader = CompositeLoader([
        FileSystemLoader(Path.home() / ".failcore" / "rulesets"),
        FileSystemLoader(default_path),
    ])
    
    registry = RuleRegistry(loader)
    registry.load_ruleset("semantic")
    
    return registry


__all__ = [
    "SemanticDetector",
]
