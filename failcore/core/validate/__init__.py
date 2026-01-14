# failcore/core/validate/__init__.py
"""
Validation subsystem (Refactored).

This module provides a complete validation architecture with:
- Stable contracts (Policy, Context, Decision)
- Unified validator interface
- Orchestration engine
- Registry for builtin
- Explain layer for decision aggregation
- Policy presets
- Plugin system

"""


# Contracts
from .contracts import (
    Policy,
    Context,
    Decision,
    ValidatorConfig,
    OverrideConfig,
    Exception,
    EnforcementMode,
    DecisionOutcome,
    RiskLevel,
)

# Validator Interface
from .validator import (
    BaseValidator,
)

# Engine
from .engine import (
    ValidationEngine,
    ValidationBlockedError,
)

# Registry
from .registry import (
    ValidatorRegistry,
)

# Constants
from .constants import (
    MetaKeys,
)

# Explain
from .explain import (
    DecisionExplanation,
    explain_decisions,
    print_explanation,
)

# Policy Presets
from .templates import (
    default_safe_policy,
    fs_safe_policy,
    net_safe_policy,
    shadow_mode_policy,
    permissive_policy,
    get_preset,
    list_presets,
)

# Bootstrap & Plugins
from .bootstrap import (
    register_builtin_validators,
    auto_register,
    is_bootstrapped,
    reset_auto_register_flag,
)

from .plugins import (
    load_plugins,
    discover_plugin_validators,
    is_plugin_system_available,
)




# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # ===== New API (v0.2.0+) =====
    
    # Contracts
    "Policy",
    "Context",
    "Decision",
    "ValidatorConfig",
    "OverrideConfig",
    "Exception",
    "EnforcementMode",
    "DecisionOutcome",
    "RiskLevel",
    
    # Validator Interface
    "BaseValidator",
    
    # Engine
    "ValidationEngine",
    "ValidationBlockedError",
    
    # Registry
    "ValidatorRegistry",
    
    # Constants
    "MetaKeys",
    
    # Explain
    "DecisionExplanation",
    "explain_decisions",
    "print_explanation",
    
    # Policy Presets
    "default_safe_policy",
    "fs_safe_policy",
    "net_safe_policy",
    "shadow_mode_policy",
    "permissive_policy",
    "get_preset",
    "list_presets",
    
    # Bootstrap & Plugins
    "register_builtin_validators",
    "auto_register",
    "is_bootstrapped",
    "reset_auto_register_flag",
    "load_plugins",
    "discover_plugin_validators",
    "is_plugin_system_available",
]


# ============================================================================
# Version Info
# ============================================================================

__version__ = "0.1.3"
__architecture_version__ = "v1"  # Contract version
