# failcore/core/config/analysis.py
"""
Analysis Configuration - controls read-only analysis features

Centralized configuration for read-only analysis features:
- drift: Parameter drift detection (default: ON)
- optimizer: Optimization suggestions (default: OFF)

Note: This config is for read-only analysis only.
For enforcement guards (semantic, taint, side-effect), see GuardConfig.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AnalysisConfig:
    """Analysis feature configuration (read-only analysis)"""
    drift: bool = True          # ✅ default ON
    optimizer: bool = False     # ❌ default OFF


# Global default configuration
_DEFAULT_CONFIG = AnalysisConfig()


def get_analysis_config(config: Optional[AnalysisConfig] = None) -> AnalysisConfig:
    """
    Get analysis configuration
    
    Args:
        config: Optional custom config (uses default if None)
    
    Returns:
        AnalysisConfig instance
    """
    return config or _DEFAULT_CONFIG


def is_drift_enabled(config: Optional[AnalysisConfig] = None) -> bool:
    """Check if drift analysis is enabled"""
    return get_analysis_config(config).drift


def is_optimizer_enabled(config: Optional[AnalysisConfig] = None) -> bool:
    """Check if optimizer analysis is enabled"""
    return get_analysis_config(config).optimizer


__all__ = [
    "AnalysisConfig",
    "get_analysis_config",
    "is_drift_enabled",
    "is_optimizer_enabled",
]
