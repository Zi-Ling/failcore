# failcore/config/modules/__init__.py
"""
Module Configuration

Configuration for five core modules: DLP, Semantic, Effects, Taint, Drift.

Design principles:
1. enabled only determines registration at startup, NOT runtime behavior
2. Each module has its own semantic configuration (no unified strict_mode)
3. YAML is input parameters, code has defaults (YAML can be deleted)
"""

from .base import ModuleConfig
from .dlp import DLPConfig
from .semantic import SemanticConfig
from .effects import EffectsConfig
from .taint import TaintConfig
from .drift import DriftConfig

__all__ = [
    "ModuleConfig",
    "DLPConfig",
    "SemanticConfig",
    "EffectsConfig",
    "TaintConfig",
    "DriftConfig",
]
