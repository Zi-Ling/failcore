# failcore/config/modules/semantic.py
"""
Semantic Module Configuration

Configuration for Semantic Intent Guard module.
"""

from dataclasses import dataclass
from typing import List, Optional
from .base import ModuleConfig
from failcore.core.rules import RuleSeverity


@dataclass(frozen=True)
class SemanticConfig(ModuleConfig):
    """
    Semantic module configuration.
    
    enabled: If True, semantic ruleset is registered at startup
    min_severity: Minimum severity to enforce (only rules >= this severity are active)
    enabled_categories: List of category strings to enable (None = all)
    """
    
    enabled: bool = False
    min_severity: RuleSeverity = RuleSeverity.HIGH
    enabled_categories: Optional[List[str]] = None
    
    @classmethod
    def default(cls) -> "SemanticConfig":
        """Default semantic configuration"""
        return cls(
            enabled=False,
            min_severity=RuleSeverity.HIGH,
            enabled_categories=None,
        )
    
    @classmethod
    def strict(cls) -> "SemanticConfig":
        """Strict semantic configuration"""
        return cls(
            enabled=True,
            min_severity=RuleSeverity.MEDIUM,  # Lower threshold = more rules active
            enabled_categories=None,  # All categories
        )
