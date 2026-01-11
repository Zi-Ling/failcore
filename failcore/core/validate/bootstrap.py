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
from .registry import get_global_registry, ValidatorRegistry
from .contracts import Context, Decision, ValidatorConfig, DecisionOutcome, RiskLevel

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
    registry: Optional[ValidatorRegistry] = None
) -> None:
    """
    Register all built-in builtin.
    
    Args:
        registry: Registry to register to (if None, uses global registry)
    """
    if registry is None:
        registry = get_global_registry()
    
    # Import builtin here to avoid circular imports
    # Note: We're wrapping legacy builtin for now
    # In the future, builtin should implement BaseValidator directly
    
    # Contract builtin
    try:
        from .builtin.contract import (
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
        from .builtin.security import path_traversal_precondition
        
        # Create a simple wrapper validator
        class PathTraversalValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "security_path_traversal"
            
            @property
            def domain(self) -> str:
                return "security"
            
            def evaluate(
                self,
                context: Context,
                config: Optional[ValidatorConfig] = None
            ) -> List[Decision]:
                # Get path parameter names from config
                path_params = ["path", "file_path", "relative_path", "filename"]
                if config and "path_params" in config.config:
                    path_params = config.config["path_params"]
                
                # Get sandbox root from config
                sandbox_root = None
                if config and "sandbox_root" in config.config:
                    sandbox_root = config.config["sandbox_root"]
                
                # Create legacy validator
                validator = path_traversal_precondition(
                    *path_params,
                    sandbox_root=sandbox_root
                )
                
                # Execute validation
                result = validator.validate(context.to_dict())
                
                # Convert to DecisionV1
                if result.valid:
                    return []
                
                return [validation_result_to_decision(result, self.id)]
        
        registry.register(PathTraversalValidator())
        logger.debug("Registered PathTraversalValidator")
    except ImportError as e:
        logger.debug(f"Failed to import security builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading security builtin: {e}")
    
    # Network builtin
    try:
        from .builtin.network import ssrf_precondition
        
        class NetworkSSRFValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "network_ssrf"
            
            @property
            def domain(self) -> str:
                return "network"
            
            def evaluate(
                self,
                context: Context,
                config: Optional[ValidatorConfig] = None
            ) -> List[Decision]:
                # Get URL parameter names from config
                url_params = ["url", "uri", "endpoint", "host"]
                if config and "url_params" in config.config:
                    url_params = config.config["url_params"]
                
                # Get other config
                allowlist = None
                block_internal = True
                allowed_schemes = None
                allowed_ports = None
                forbid_userinfo = True
                
                if config:
                    allowlist = config.config.get("allowlist")
                    block_internal = config.config.get("block_internal", True)
                    if "allowed_schemes" in config.config:
                        allowed_schemes = set(config.config["allowed_schemes"])
                    if "allowed_ports" in config.config:
                        allowed_ports = set(config.config["allowed_ports"])
                    forbid_userinfo = config.config.get("forbid_userinfo", True)
                
                # Create legacy validator
                validator = ssrf_precondition(
                    *url_params,
                    allowlist=allowlist,
                    block_internal=block_internal,
                    allowed_schemes=allowed_schemes,
                    allowed_ports=allowed_ports,
                    forbid_userinfo=forbid_userinfo,
                )
                
                # Execute validation
                result = validator.validate(context.to_dict())
                
                # Convert to DecisionV1
                if result.valid:
                    return []
                
                return [validation_result_to_decision(result, self.id)]
        
        registry.register(NetworkSSRFValidator())
        logger.debug("Registered NetworkSSRFValidator")
    except ImportError as e:
        logger.debug(f"Failed to import network builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading network builtin: {e}")
    
    # Resource builtin
    try:
        from .builtin.resource import (
            max_file_size_precondition,
            max_payload_size_precondition,
        )
        
        class ResourceFileSizeValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "resource_file_size"
            
            @property
            def domain(self) -> str:
                return "resource"
            
            def evaluate(
                self,
                context: Context,
                config: Optional[ValidatorConfig] = None
            ) -> List[Decision]:
                param_name = "path"
                max_bytes = 100 * 1024 * 1024  # 100MB default
                
                if config:
                    param_name = config.config.get("param_name", param_name)
                    max_bytes = config.config.get("max_bytes", max_bytes)
                
                # Create legacy validator
                validator = max_file_size_precondition(param_name, max_bytes=max_bytes)
                
                # Execute validation
                result = validator.validate(context.to_dict())
                
                # Convert to DecisionV1
                if result.valid:
                    return []
                
                return [validation_result_to_decision(result, self.id)]
        
        registry.register(ResourceFileSizeValidator())
        logger.debug("Registered ResourceFileSizeValidator")
    except ImportError as e:
        logger.debug(f"Failed to import resource builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading resource builtin: {e}")
    
    # Type builtin
    try:
        from .builtin.type import (
            type_check_precondition,
            required_fields_precondition,
        )
        
        class TypeRequiredFieldsValidator(BaseValidator):
            @property
            def id(self) -> str:
                return "type_required_fields"
            
            @property
            def domain(self) -> str:
                return "type"
            
            def evaluate(
                self,
                context: Context,
                config: Optional[ValidatorConfig] = None
            ) -> List[Decision]:
                if not config or "required_fields" not in config.config:
                    return []
                
                required_fields = config.config["required_fields"]
                
                # Create legacy validator
                validator = required_fields_precondition(*required_fields)
                
                # Execute validation
                result = validator.validate(context.to_dict())
                
                # Convert to DecisionV1
                if result.valid:
                    return []
                
                return [validation_result_to_decision(result, self.id)]
        
        registry.register(TypeRequiredFieldsValidator())
        logger.debug("Registered TypeRequiredFieldsValidator")
    except ImportError as e:
        logger.debug(f"Failed to import type builtin: {e}")
    except Exception as e:
        logger.warning(f"Error loading type builtin: {e}")


def is_bootstrapped(registry: Optional[ValidatorRegistry] = None) -> bool:
    """
    Check if built-in builtin are registered.
    
    Args:
        registry: Registry to check (if None, uses global registry)
    
    Returns:
        True if at least one built-in validator is registered
    """
    if registry is None:
        registry = get_global_registry()
    
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


__all__ = [
    "register_builtin_validators",
    "is_bootstrapped",
    "auto_register",
    "reset_auto_register_flag",
]
