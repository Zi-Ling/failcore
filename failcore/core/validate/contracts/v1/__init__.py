# failcore/core/validate/contracts/v1/__init__.py
"""
Validation Contract V1.

This is the stable contract for validation system.
Fields are append-only and semantically stable.
"""

from .policy import (
    PolicyV1,
    ValidatorConfigV1,
    OverrideConfigV1,
    ExceptionV1,
    EnforcementMode,
)

from .context import ContextV1

from .decision import (
    DecisionV1,
    DecisionOutcome,
    RiskLevel,
)

__all__ = [
    # Policy
    "PolicyV1",
    "ValidatorConfigV1",
    "OverrideConfigV1",
    "ExceptionV1",
    "EnforcementMode",
    
    # Context
    "ContextV1",
    
    # Decision
    "DecisionV1",
    "DecisionOutcome",
    "RiskLevel",
]
