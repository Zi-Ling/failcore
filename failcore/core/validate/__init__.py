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

New Architecture (v0.2.0):
```
validate/
  contracts/v1/       # Stable contracts (PolicyV1, ContextV1, DecisionV1)
  validator.py        # Unified validator interface
  engine.py           # Orchestration layer
  registry.py         # Validator registry
  explain.py          # Decision explanation
  presets.py          # Policy templates
  plugins.py          # Plugin system
  bootstrap.py        # Built-in validator registration
  builtin/         # Validator implementations (legacy)
```

Quick Start (New API):
```python
from failcore.core.validate import (
    ValidationEngine,
    ContextV1,
    PolicyV1,
    get_global_registry,
    auto_register,
    default_safe_policy,
)

# 1. Bootstrap built-in builtin
auto_register()

# 2. Create policy
policy = default_safe_policy()

# 3. Create engine
engine = ValidationEngine(policy=policy, registry=get_global_registry())

# 4. Validate
context = ContextV1(
    tool="http_get",
    params={"url": "http://example.com"}
)

decisions = engine.evaluate(context)

# 5. Check results
if any(d.is_blocking for d in decisions):
    print("Validation blocked!")
```

Legacy API (Backward Compatible):
```python
from failcore.core.validate import (
    ValidationResult,
    PreconditionValidator,
    PostconditionValidator,
    ValidatorRegistry as LegacyRegistry,
)

# Old API still works
```
"""

# ============================================================================
# New API (v0.2.0+)
# ============================================================================

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
    get_global_registry,
    set_global_registry,
    reset_global_registry,
)

# Explain
from .explain import (
    DecisionExplanation,
    explain_decisions,
    print_explanation,
)

# Policy Presets
from .presets import (
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
    "get_global_registry",
    "set_global_registry",
    "reset_global_registry",
    
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
