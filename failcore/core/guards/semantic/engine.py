# failcore/core/guards/semantic/engine.py
"""
Semantic Engine

Real and NoOp implementations of Semantic intent guard engine.
"""

from typing import Dict, Any
from .types import SemanticResult, SemanticAction, SemanticViolation
from failcore.core.rules import RuleRegistry, RuleEngine, RuleCategory, RuleSeverity, RuleAction


class SemanticEngine:
    """
    Semantic intent guard engine interface
    
    Both RealSemanticEngine and NoOpSemanticEngine implement this interface.
    """
    
    def check(self, tool_name: str, params: Dict[str, Any]) -> SemanticResult:
        """
        Check tool call for semantic violations
        
        Args:
            tool_name: Tool name
            params: Tool parameters
        
        Returns:
            SemanticResult with verdict and violations
        """
        raise NotImplementedError


class RealSemanticEngine(SemanticEngine):
    """
    Real Semantic engine implementation
    
    Uses rule registry and engine to detect malicious intent.
    """
    
    def __init__(
        self,
        rule_registry: RuleRegistry,
        rule_engine: RuleEngine,
        min_severity: RuleSeverity = RuleSeverity.HIGH,
        enabled_categories: list[str] = None,
    ):
        """
        Initialize real Semantic engine
        
        Args:
            rule_registry: Rule registry with semantic rules loaded
            rule_engine: Rule engine for evaluation
            min_severity: Minimum severity to enforce
            enabled_categories: List of enabled categories (None = all)
        """
        self.rule_registry = rule_registry
        self.rule_engine = rule_engine
        self.min_severity = min_severity
        self.enabled_categories = enabled_categories
    
    def check(self, tool_name: str, params: Dict[str, Any]) -> SemanticResult:
        """Check tool call using semantic rules"""
        # Determine categories to check
        categories = None
        if self.enabled_categories:
            category_map = {
                "semantic.secret_leakage": RuleCategory.SEMANTIC_SECRET_LEAKAGE,
                "semantic.injection": RuleCategory.SEMANTIC_INJECTION,
                "semantic.dangerous_combo": RuleCategory.SEMANTIC_DANGEROUS_COMBO,
                "semantic.path_traversal": RuleCategory.SEMANTIC_PATH_TRAVERSAL,
            }
            categories = [category_map.get(c) for c in self.enabled_categories if c in category_map]
        
        # Evaluate using rule engine
        result = self.rule_engine.evaluate(
            tool_name=tool_name,
            params=params,
            categories=categories,
            min_severity=self.min_severity,
        )
        
        # Convert rule matches to violations
        violations = []
        for match in result.matches:
            violation = SemanticViolation(
                rule_id=match.rule.rule_id,
                rule_name=match.rule.name,
                category=match.rule.category.value,
                severity=match.rule.severity.value,
                description=match.rule.description,
            )
            violations.append(violation)
        
        # Map RuleAction to SemanticAction
        action_map = {
            RuleAction.BLOCK: SemanticAction.BLOCK,
            RuleAction.WARN: SemanticAction.WARN,
            RuleAction.LOG: SemanticAction.LOG,
            RuleAction.ALLOW: SemanticAction.ALLOW,
        }
        action = action_map.get(result.action, SemanticAction.WARN)
        
        return SemanticResult(
            action=action,
            violations=violations,
            reason="ok",
            confidence=result.confidence,
            evidence={
                "matched_rule_ids": [m.rule.rule_id for m in result.matches],
                "highest_severity": result.highest_severity.value if result.highest_severity else None,
            },
        )


class NoOpSemanticEngine(SemanticEngine):
    """
    NoOp Semantic engine when module is disabled
    
    Returns allow verdict with reason="disabled" for observability.
    """
    
    def check(self, tool_name: str, params: Dict[str, Any]) -> SemanticResult:
        """NoOp check - returns allow verdict"""
        return SemanticResult(
            action=SemanticAction.ALLOW,
            violations=[],
            reason="disabled",
            confidence=1.0,
            evidence={
                "status": "disabled",
            },
        )
    
    def __repr__(self) -> str:
        return "NoOpSemanticEngine(disabled)"


__all__ = [
    "SemanticEngine",
    "RealSemanticEngine",
    "NoOpSemanticEngine",
]
