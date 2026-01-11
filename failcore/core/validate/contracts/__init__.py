# failcore/core/validate/contracts/__init__.py
"""
Stable validation contracts.

These contracts define the interface between validation engines,
policy data, and decision outputs. They are designed to be:
- Platform-agnostic (serializable, no runtime-specific objects)
- Versioned (v1, v2, etc.)
- Stable (append-only, no breaking changes)

This allows FailCore to migrate across platforms (Python, Rust, WASM, mobile)
without breaking policies or tooling.
"""




from .v1 import (
    # Core contracts
    PolicyV1 as Policy,
    ContextV1 as Context,
    DecisionV1 as Decision,
    
    # Supporting types
    ValidatorConfigV1 as ValidatorConfig,
    OverrideConfigV1 as OverrideConfig,
    ExceptionV1 as Exception,

    EnforcementMode,
    DecisionOutcome,
    RiskLevel,
)

__all__ = [
    # Core contracts
    "Policy",
    "Context",
    "Decision",
    
    # Supporting types
    "ValidatorConfig",
    "OverrideConfig",
    "Exception",

    "EnforcementMode",
    "DecisionOutcome",
    "RiskLevel",
]
