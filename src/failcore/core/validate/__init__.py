# failcore/core/validate/__init__.py
"""
Validation subsystem.

Provides:
- Precondition validators (fail-fast checks before execution)
- Postcondition validators (output contract checks)
- Validator registry and result types
- Integration with the contract layer (contract drift detection)
"""

from .validator import (
    ValidationResult,
    ValidationError,
    Validator,
    PreconditionValidator,
    PostconditionValidator,
    ValidatorRegistry,
    file_exists_precondition,
    file_not_exists_precondition,
    dir_exists_precondition,
    param_not_empty_precondition,
)

from .validators.contract import (
    output_contract_postcondition,
    json_output_postcondition,
    text_output_postcondition,
)

from .rules import (
    RuleAssembler,
    ValidationRuleSet,
)

from .presets import (
    ValidationPreset,
    fs_safe_sandbox,
    net_safe,
    resource_limits,
    basic_param_contracts,
    output_contract,
    combined_safe,
)

__all__ = [
    # Core validation primitives
    "ValidationResult",
    "ValidationError",
    "Validator",
    "PreconditionValidator",
    "PostconditionValidator",
    "ValidatorRegistry",
    # Common preconditions
    "file_exists_precondition",
    "file_not_exists_precondition",
    "dir_exists_precondition",
    "param_not_empty_precondition",
    # Contract validators
    "output_contract_postcondition",
    "json_output_postcondition",
    "text_output_postcondition",
    # Rule
    "RuleAssembler",
    "ValidationRuleSet",
    # Presets
    "ValidationPreset",
    "fs_safe_sandbox",
    "net_safe",
    "resource_limits",
    "basic_param_contracts",
    "output_contract",
    "combined_safe",
]
