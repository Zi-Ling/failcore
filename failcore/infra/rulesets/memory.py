# failcore/infra/rulesets/memory.py
"""
Memory RuleSet Loader

In-memory loader for testing and programmatic rule creation
"""

from __future__ import annotations

from typing import List, Optional, Dict

from failcore.core.rules.loader import RuleSetLoader
from failcore.core.rules.models import RuleSet


class MemoryLoader(RuleSetLoader):
    """
    Load rulesets from memory
    
    Useful for:
    - Testing
    - Programmatic rule creation
    - Dynamic rule modification
    """
    
    def __init__(self, rulesets: Optional[Dict[str, RuleSet]] = None):
        """
        Initialize memory loader
        
        Args:
            rulesets: Optional dict of ruleset_name -> RuleSet
        """
        self._rulesets: Dict[str, RuleSet] = rulesets or {}
    
    def load_ruleset(self, name: str) -> Optional[RuleSet]:
        """Load a ruleset by name"""
        return self._rulesets.get(name)
    
    def list_available_rulesets(self) -> List[str]:
        """List all available ruleset names"""
        return list(self._rulesets.keys())
    
    def reload(self) -> None:
        """Reload (no-op for memory loader)"""
        pass
    
    def add_ruleset(self, ruleset: RuleSet) -> None:
        """
        Add a ruleset to memory
        
        Args:
            ruleset: RuleSet to add
        """
        self._rulesets[ruleset.name] = ruleset
    
    def remove_ruleset(self, name: str) -> bool:
        """
        Remove a ruleset from memory
        
        Args:
            name: Ruleset name to remove
        
        Returns:
            True if removed, False if not found
        """
        if name in self._rulesets:
            del self._rulesets[name]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all rulesets"""
        self._rulesets.clear()


__all__ = ["MemoryLoader"]
