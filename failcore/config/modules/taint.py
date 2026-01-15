# failcore/config/modules/taint.py
"""
Taint Module Configuration

Configuration for Taint Tracking module.
"""

from dataclasses import dataclass
from typing import Literal
from .base import ModuleConfig


@dataclass(frozen=True)
class TaintConfig(ModuleConfig):
    """
    Taint module configuration.
    
    enabled: If True, taint tracking is registered at startup
    propagation_mode: Propagation mode (whole/paths)
    max_path_depth: Maximum depth for path-level tracking
    max_paths_per_step: Maximum paths to track per step
    """
    
    enabled: bool = False
    propagation_mode: Literal["whole", "paths"] = "whole"
    max_path_depth: int = 3
    max_paths_per_step: int = 100
    
    @classmethod
    def default(cls) -> "TaintConfig":
        """Default taint configuration"""
        return cls(
            enabled=False,
            propagation_mode="whole",
            max_path_depth=3,
            max_paths_per_step=100,
        )
    
    @classmethod
    def strict(cls) -> "TaintConfig":
        """Strict taint configuration"""
        return cls(
            enabled=True,
            propagation_mode="paths",  # More detailed tracking
            max_path_depth=3,
            max_paths_per_step=100,
        )
