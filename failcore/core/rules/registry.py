# failcore/core/rules/registry.py
"""
Rule Registry

Central registry for managing and querying rules
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set
from collections import defaultdict

from .models import Rule, RuleSet, RuleCategory, RuleSeverity, RuleAction
from .loader import RuleSetLoader


class RuleRegistry:
    """
    Central rule registry
    
    Manages rules from multiple rulesets and provides query interface
    """
    
    def __init__(self, loader: Optional[RuleSetLoader] = None):
        """
        Initialize rule registry
        
        Args:
            loader: RuleSetLoader to use for loading rulesets
        """
        self.loader = loader
        self._rules: Dict[str, Rule] = {}  # rule_id -> Rule
        self._rules_by_category: Dict[RuleCategory, List[Rule]] = defaultdict(list)
        self._rules_by_severity: Dict[RuleSeverity, List[Rule]] = defaultdict(list)
        self._rulesets: Dict[str, RuleSet] = {}  # ruleset_name -> RuleSet
    
    def load_ruleset(self, name: str) -> bool:
        """
        Load a ruleset
        
        Args:
            name: Ruleset name (e.g., "dlp", "semantic")
        
        Returns:
            True if loaded successfully
        """
        if not self.loader:
            return False
        
        ruleset = self.loader.load_ruleset(name)
        if not ruleset:
            return False
        
        self.register_ruleset(ruleset)
        return True
    
    def register_ruleset(self, ruleset: RuleSet) -> None:
        """
        Register a ruleset
        
        Args:
            ruleset: RuleSet to register
        """
        self._rulesets[ruleset.name] = ruleset
        
        for rule in ruleset.rules:
            self.register_rule(rule)
    
    def register_rule(self, rule: Rule) -> None:
        """
        Register a single rule
        
        Args:
            rule: Rule to register
        """
        self._rules[rule.rule_id] = rule
        self._rules_by_category[rule.category].append(rule)
        self._rules_by_severity[rule.severity].append(rule)
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID"""
        return self._rules.get(rule_id)
    
    def get_rules_by_category(self, category: RuleCategory) -> List[Rule]:
        """Get all rules in a category"""
        return [r for r in self._rules_by_category.get(category, []) if r.enabled]
    
    def get_rules_by_severity(self, min_severity: RuleSeverity) -> List[Rule]:
        """Get all rules with severity >= min_severity"""
        severity_order = {
            RuleSeverity.LOW: 1,
            RuleSeverity.MEDIUM: 2,
            RuleSeverity.HIGH: 3,
            RuleSeverity.CRITICAL: 4,
        }
        
        min_level = severity_order.get(min_severity, 1)
        
        rules = []
        for severity, level in severity_order.items():
            if level >= min_level:
                rules.extend([r for r in self._rules_by_severity.get(severity, []) if r.enabled])
        
        return rules
    
    def get_all_rules(self) -> List[Rule]:
        """Get all registered rules"""
        return [r for r in self._rules.values() if r.enabled]
    
    def get_ruleset(self, name: str) -> Optional[RuleSet]:
        """Get ruleset by name"""
        return self._rulesets.get(name)
    
    def list_rulesets(self) -> List[str]:
        """List all registered ruleset names"""
        return list(self._rulesets.keys())
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule"""
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule"""
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False
    
    def count(self) -> int:
        """Count total rules"""
        return len(self._rules)
    
    def count_enabled(self) -> int:
        """Count enabled rules"""
        return sum(1 for r in self._rules.values() if r.enabled)
    
    def reload(self) -> None:
        """Reload all rulesets from loader"""
        if not self.loader:
            return
        
        # Clear current rules
        self._rules.clear()
        self._rules_by_category.clear()
        self._rules_by_severity.clear()
        self._rulesets.clear()
        
        # Reload loader
        self.loader.reload()
        
        # Load all available rulesets
        for name in self.loader.list_available_rulesets():
            self.load_ruleset(name)


__all__ = [
    "RuleRegistry",
]
