# failcore/core/rules/loader.py
"""
Rule Loader Interface

Defines the interface for loading rulesets from various sources
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path

from .models import RuleSet


class RuleSetLoader(ABC):
    """
    Abstract interface for loading rulesets
    
    Implementations:
    - FileSystemLoader: Load from YAML files
    - MemoryLoader: Load from memory (for testing)
    - RemoteLoader: Load from remote sources (future)
    """
    
    @abstractmethod
    def load_ruleset(self, name: str) -> Optional[RuleSet]:
        """
        Load a ruleset by name
        
        Args:
            name: Ruleset name (e.g., "dlp", "semantic")
        
        Returns:
            RuleSet if found, None otherwise
        """
        pass
    
    @abstractmethod
    def list_available_rulesets(self) -> List[str]:
        """
        List all available ruleset names
        
        Returns:
            List of ruleset names
        """
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """Reload all rulesets from source"""
        pass


class CompositeLoader(RuleSetLoader):
    """
    Composite loader that tries multiple loaders in order
    
    Example:
        loader = CompositeLoader([
            FileSystemLoader("~/.failcore/rulesets"),
            FileSystemLoader("/etc/failcore/rulesets"),
            FileSystemLoader("failcore/config/rulesets/default"),
        ])
    """
    
    def __init__(self, loaders: List[RuleSetLoader]):
        """
        Initialize composite loader
        
        Args:
            loaders: List of loaders to try in order
        """
        self.loaders = loaders
    
    def load_ruleset(self, name: str) -> Optional[RuleSet]:
        """Load ruleset from first loader that has it"""
        for loader in self.loaders:
            ruleset = loader.load_ruleset(name)
            if ruleset:
                return ruleset
        return None
    
    def list_available_rulesets(self) -> List[str]:
        """List all available rulesets from all loaders"""
        names = set()
        for loader in self.loaders:
            names.update(loader.list_available_rulesets())
        return sorted(names)
    
    def reload(self) -> None:
        """Reload all loaders"""
        for loader in self.loaders:
            loader.reload()


__all__ = [
    "RuleSetLoader",
    "CompositeLoader",
]
