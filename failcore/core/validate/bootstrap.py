# failcore/core/validate/bootstrap.py
"""
Bootstrap: Register built-in builtin.

This module registers all built-in builtin with the global registry.

Design principles:
- Keep existing validator implementations unchanged
- Use adapters for backward compatibility
- Register builtin on module import
- Support lazy loading
"""

from __future__ import annotations

from typing import List, Optional
import logging

from .validator import BaseValidator
from .registry import ValidatorRegistry
from .contracts import Context, Decision, ValidatorConfig, DecisionOutcome, RiskLevel, Policy
from .engine import ValidationEngine

try:
    from ..errors.exceptions import FailCoreError
    from ..errors import codes
except ImportError:
    # Fallback if errors module is not available
    FailCoreError = ValueError  # type: ignore
    codes = None  # type: ignore

logger = logging.getLogger(__name__)


def validation_result_to_decision(result, validator_id: str, rule_id: Optional[str] = None) -> Decision:
    """
    Convert legacy ValidationResult to DecisionV1.
    
    Helper function for bootstrap adapters.
    """
    # Map severity to decision outcome
    severity_map = {
        "ok": DecisionOutcome.ALLOW,
        "warn": DecisionOutcome.WARN,
        "block": DecisionOutcome.BLOCK,
    }
    
    decision_outcome = severity_map.get(
        getattr(result, 'severity', 'ok'),
        DecisionOutcome.ALLOW
    )
    
    # Determine risk level
    risk_level = RiskLevel.MEDIUM
    if decision_outcome == DecisionOutcome.BLOCK:
        risk_level = RiskLevel.HIGH
    elif decision_outcome == DecisionOutcome.WARN:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW
    
    # Extract code
    code = getattr(result, 'code', None) or f"FC_LEGACY_{validator_id.upper()}"
    
    # Build evidence
    evidence = getattr(result, 'details', {})
    if hasattr(result, 'validator'):
        evidence['legacy_validator'] = result.validator
    if hasattr(result, 'vtype'):
        evidence['validation_type'] = str(result.vtype)
    
    return Decision(
        decision=decision_outcome,
        code=code,
        validator_id=validator_id,
        rule_id=rule_id,
        message=getattr(result, 'message', ''),
        evidence=evidence,
        risk_level=risk_level,
        tool=getattr(result, 'tool', None),
    )


def register_builtin_validators(
    registry: ValidatorRegistry
) -> None:
    """
    Register all built-in builtin.
    
    Args:
        registry: Registry to register to (required, no global registry)
    """
    if registry is None:
        raise ValueError("registry parameter is required (no global registry)")
    
    # Import builtin here to avoid circular imports
    # Note: We're wrapping legacy builtin for now
    # In the future, builtin should implement BaseValidator directly
    
    # Contract builtin
    try:
        from failcore.core.validate.builtin.output.contract import (
            output_contract_postcondition,
            json_output_postcondition,
            text_output_postcondition,
        )
        
        # These are postcondition builtin, we'll register them as adapters
        # For now, we'll skip these and focus on precondition builtin
    except ImportError as e:
        logger.debug(f"Failed to import contract builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading contract builtin: {e}")
    
    # Security builtin
    try:
        from failcore.core.validate.builtin.pre.security import PathTraversalValidator
        
        registry.register(PathTraversalValidator())
        logger.debug("Registered PathTraversalValidator")
    except ImportError as e:
        logger.debug(f"Failed to import security builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading security builtin: {e}")
    
    # DLP guard builtin
    try:
        from failcore.core.validate.builtin.output.dlp import DLPGuardValidator
        
        registry.register(DLPGuardValidator())
        logger.debug("Registered DLPGuardValidator")
    except ImportError as e:
        logger.debug(f"Failed to import DLP builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading DLP builtin: {e}")
    
    # Semantic intent builtin
    try:
        from failcore.core.validate.builtin.output.semantic import SemanticIntentValidator
        
        registry.register(SemanticIntentValidator())
        logger.debug("Registered SemanticIntentValidator")
    except ImportError as e:
        logger.debug(f"Failed to import semantic builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading semantic builtin: {e}")
    
    # Taint flow builtin
    try:
        from failcore.core.validate.builtin.output.taint import TaintFlowValidator
        
        registry.register(TaintFlowValidator())
        logger.debug("Registered TaintFlowValidator")
    except ImportError as e:
        logger.debug(f"Failed to import taint flow builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading taint flow builtin: {e}")
    
    # Post-run drift builtin
    try:
        from failcore.core.validate.builtin.post.drift import PostRunDriftValidator
        
        registry.register(PostRunDriftValidator())
        logger.debug("Registered PostRunDriftValidator")
    except ImportError as e:
        logger.debug(f"Failed to import drift builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading drift builtin: {e}")
    
    # Network builtin
    try:
        from failcore.core.validate.builtin.pre.network import NetworkSSRFValidator
        
        registry.register(NetworkSSRFValidator())
        logger.debug("Registered NetworkSSRFValidator")
    except ImportError as e:
        logger.debug(f"Failed to import network builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading network builtin: {e}")
    
    # Resource builtin
    try:
        from failcore.core.validate.builtin.pre.resource import ResourceFileSizeValidator
        
        registry.register(ResourceFileSizeValidator())
        logger.debug("Registered ResourceFileSizeValidator")
    except ImportError as e:
        logger.debug(f"Failed to import resource builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading resource builtin: {e}")
    
    # Type builtin
    try:
        from failcore.core.validate.builtin.pre.schema import TypeRequiredFieldsValidator
        
        registry.register(TypeRequiredFieldsValidator())
        logger.debug("Registered TypeRequiredFieldsValidator")
    except ImportError as e:
        logger.debug(f"Failed to import type builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading type builtin: {e}")


def is_bootstrapped(registry: ValidatorRegistry) -> bool:
    """
    Check if built-in builtin are registered.
    
    Args:
        registry: Registry to check (required, no global registry)
    
    Returns:
        True if at least one built-in validator is registered
    """
    if registry is None:
        raise ValueError("registry parameter is required (no global registry)")
    
    return registry.count() > 0


# Auto-register on import
_auto_registered = False


def auto_register() -> None:
    """Auto-register built-in builtin on first call"""
    global _auto_registered
    if not _auto_registered:
        register_builtin_validators()
        _auto_registered = True


def reset_auto_register_flag() -> None:
    """
    Reset the auto-register flag.
    
    This is useful for testing when you need to re-register builtin
    after calling reset_global_registry().
    """
    global _auto_registered
    _auto_registered = False


def create_default_registry() -> ValidatorRegistry:
    """
    Create and register builtin validators registry (factory function).
    
    This function creates a new ValidatorRegistry instance and registers all
    builtin validators. Each call creates a new instance (maintains extractability).
    
    For performance, use application-level singleton (see api/context.py).
    
    Returns:
        New ValidatorRegistry instance with builtin validators registered
    """
    registry = ValidatorRegistry()
    register_builtin_validators(registry)
    return registry


def ensure_registered(registry: ValidatorRegistry, policy: Policy) -> None:
    """
    Ensure all validators required by policy are registered.
    
    If any validator is missing, raises FailCoreError with clear fix guidance.
    
    Args:
        registry: Validator registry to check
        policy: Policy to check against
    
    Raises:
        FailCoreError: If any required validator is missing from registry
    """
    if registry is None:
        if FailCoreError != ValueError:
            raise FailCoreError.validation(
                message="registry parameter is required",
                error_code=codes.INVALID_ARGUMENT if codes else "INVALID_ARGUMENT",
            )
        else:
            raise ValueError("registry parameter is required")
    
    if policy is None:
        return  # No policy to check
    
    # Get all validator IDs from policy (policy.validators is Dict[str, ValidatorConfig])
    required_ids = set(policy.validators.keys())
    
    if not required_ids:
        return  # No validators required
    
    # Check which validators are missing
    missing = []
    for validator_id in required_ids:
        if registry.get(validator_id) is None:
            missing.append(validator_id)
    
    if missing:
        policy_name = policy.metadata.get("name", "unknown") if policy.metadata else "unknown"
        # Get available validator IDs
        available_ids = sorted([v.id for v in registry.list_validators()])
        
        message = f"Missing validators for policy '{policy_name}': {', '.join(missing)}"
        suggestion = (
            "Use create_default_registry() or create_default_engine() to automatically register builtin validators. "
            "Or use get_default_registry() from failcore.api if available."
        )
        
        if FailCoreError != ValueError and codes:
            raise FailCoreError(
                message=message,
                error_code=codes.INVALID_ARGUMENT,
                error_type="VALIDATION_ERROR",
                phase="validate",
                details={
                    "policy_name": policy_name,
                    "missing_validators": missing,
                    "available_validators": available_ids,
                },
                suggestion=suggestion,
            )
        else:
            raise ValueError(f"{message}. {suggestion}. Available validators: {', '.join(available_ids)}")


def create_default_engine(
    policy: Optional[Policy] = None,
    registry: Optional[ValidatorRegistry] = None,
    strict_mode: bool = False,
) -> ValidationEngine:
    """
    Create default validation engine (factory function).
    
    This function creates a new ValidationEngine instance. Engine is created
    new each time (may have state). Registry can be injected or created new.
    
    Args:
        policy: Validation policy (if None, uses default policy)
        registry: Validator registry (if None, creates new registry)
        strict_mode: If True, short-circuit on first BLOCK decision
    
    Returns:
        New ValidationEngine instance
    
    Note:
        - Engine is created new each time (may have state)
        - Registry can be reused (recommended for performance)
        - If registry is None, creates new registry (maintains extractability)
        - For performance, inject application-level registry singleton
        - Validators are checked before engine creation (fail-fast)
    """
    if registry is None:
        registry = create_default_registry()
    
    # Ensure all required validators are registered BEFORE creating engine (fail-fast)
    if policy:
        ensure_registered(registry, policy)
    
    engine = ValidationEngine(registry=registry, policy=policy, strict_mode=strict_mode)
    
    return engine


__all__ = [
    "register_builtin_validators",
    "is_bootstrapped",
    "auto_register",
    "reset_auto_register_flag",
    "create_default_registry",
    "ensure_registered",
    "create_default_engine",
]
