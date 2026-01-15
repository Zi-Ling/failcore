# failcore/config/__init__.py
"""
FailCore Configuration

Unified configuration system for all modules.

Design principles:
1. enabled only determines registration at startup, NOT runtime behavior
2. Each module has its own semantic configuration (no unified strict_mode)
3. YAML is input parameters, code has defaults (YAML can be deleted)
"""

# Module configurations
from .modules import (
    ModuleConfig,
    DLPConfig,
    SemanticConfig,
    EffectsConfig,
    TaintConfig,
    DriftConfig,
)

# Core configurations
from .limits import LimitsConfig
from .cost import (
    USAGE_CANDIDATE_PATHS,
    KNOWN_PROVIDER_REPORTED,
    COST_CONFLICT_THRESHOLD,
    STANDARD_TOKEN_FIELDS,
)
from .proxy import ProxyConfig
from .analysis import AnalysisConfig
from .boundaries import get_boundary, list_presets

# Unified configuration
from .loader import FailCoreConfig, load_config

# Validator
from .validator import validate_config, ConfigIssue, ConfigWarning

# Capability (re-export from runtime for convenience)
from failcore.core.runtime.capability import RuntimeCapabilities, ModuleCapability, build_capabilities

__all__ = [
    # Module configs
    "ModuleConfig",
    "DLPConfig",
    "SemanticConfig",
    "EffectsConfig",
    "TaintConfig",
    "DriftConfig",
    
    # Core configs
    "LimitsConfig",
    "ProxyConfig",
    "AnalysisConfig",
    
    # Cost config
    "USAGE_CANDIDATE_PATHS",
    "KNOWN_PROVIDER_REPORTED",
    "COST_CONFLICT_THRESHOLD",
    "STANDARD_TOKEN_FIELDS",
    
    # Boundaries
    "get_boundary",
    "list_presets",
    
    # Unified config
    "FailCoreConfig",
    "load_config",
    
    # Validator
    "validate_config",
    "ConfigIssue",
    "ConfigWarning",  # Alias for backward compatibility
    
    # Capability
    "RuntimeCapabilities",
    "ModuleCapability",
    "build_capabilities",
]
