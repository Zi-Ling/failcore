# \failcore\core\tools\registry.py

from typing import Callable, Dict, Optional, Any, List, TYPE_CHECKING
import os

if TYPE_CHECKING:
    from ..validate import Policy

# ---------------------------
# Tool Registry
# ---------------------------

ToolFn = Callable[..., Any]


class ToolRegistry:
    """
    Enhanced tool registry with metadata and validation policy management
    
    Features:
    - Tool metadata tracking (risk_level, side_effect, default_action)
    - Automatic validation policy creation based on metadata
    - Strict mode enforcement for HIGH risk tools
    - Validator registration and management
    """
    def __init__(self, sandbox_root: Optional[str] = None) -> None:
        """
        Initialize tool registry
        
        Args:
            sandbox_root: Sandbox root directory for path validation
        """
        from .spec import ToolSpec
        from ..validate import Policy, ValidationEngine, ValidatorRegistry
        
        self._tools: Dict[str, ToolFn] = {}
        self._specs: Dict[str, ToolSpec] = {}  # Store full ToolSpec
        self._policies: Dict[str, Policy] = {}  # tool_name -> policy
        self._validators: Dict[str, List] = {}  # tool_name -> [validators]
        
        # Validation components
        self.sandbox_root = sandbox_root or os.getcwd()
        self._validator_registry = ValidatorRegistry()
        self._validation_engine = ValidationEngine(
            registry=self._validator_registry,
            policy=None,  # Will be set per tool
            strict_mode=False
        )

    def register(self, name: str, fn: ToolFn) -> None:
        """
        Basic registration (backward compatible)
        """
        if not name or not isinstance(name, str):
            raise ValueError("tools name must be non-empty str")
        if not callable(fn):
            raise ValueError("tools fn must be callable")
        self._tools[name] = fn
    
    def register_tool(
        self,
        spec: 'ToolSpec',
        policy: Optional['Policy'] = None,
        auto_assemble: bool = True,
    ) -> None:
        """
        Register a tool with full metadata and validation      
        Args:
            spec: ToolSpec with metadata
            policy: Optional validation policy
            auto_assemble: Auto-assemble validation policy based on metadata
            
        Raises:
            ValueError: If HIGH risk tool lacks strict validation
        """
        from .metadata import validate_metadata_runtime, RiskLevel
        from ..validate import fs_safe_policy, net_safe_policy, default_safe_policy
        
        name = spec.name
        
        # Validate metadata constraints
        # Consider strict mode enabled if: policy provided OR auto_assemble will create policy
        has_strict = policy is not None or auto_assemble
        
        try:
            validate_metadata_runtime(spec.tool_metadata, strict_enabled=has_strict)
        except ValueError as e:
            raise ValueError(f"Tool '{name}' metadata validation failed: {e}")
        
        # Store tool and spec
        self._tools[name] = spec.fn
        self._specs[name] = spec
        
        # Store policy if provided
        if policy:
            self._policies[name] = policy
        
        # Auto-assemble validation policy if enabled
        elif auto_assemble:
            policy = self._create_policy_from_metadata(spec)
            if policy:
                self._policies[name] = policy
        
        # For HIGH risk tools without validation, raise error
        if spec.tool_metadata.risk_level == RiskLevel.HIGH:
            if name not in self._policies:
                if not has_strict:
                    raise ValueError(
                        f"HIGH risk tool '{name}' must have strict validation. "
                        f"Either provide a policy or enable auto_assemble with proper metadata."
                    )
    
    def _create_policy_from_metadata(self, spec: 'ToolSpec') -> Optional['Policy']:
        """
        Create validation policy based on tool metadata.
        
        Args:
            spec: ToolSpec with metadata
            
        Returns:
            Policy instance or None if no validation needed
        """
        from .metadata import SideEffect
        from ..validate import fs_safe_policy, net_safe_policy, default_safe_policy
        
        side_effect = spec.tool_metadata.side_effect
        
        # Choose policy based on side effect type
        if side_effect == SideEffect.FS:
            return fs_safe_policy(sandbox_root=self.sandbox_root)
        elif side_effect == SideEffect.NETWORK:
            # Get network allowlist from extras if available
            allowlist = spec.extras.get("network_allowlist")
            return net_safe_policy(allowlist=allowlist)
        elif side_effect in (SideEffect.EXEC, SideEffect.PROCESS):
            return default_safe_policy()
        else:
            # No side effects, no validation needed
            return None
    
    def register_validator(self, tool_name: str, validator) -> None:
        """
        Register validator for a tool    
        Args:
            tool_name: Tool name
            validator: BaseValidator instance
        """
        if tool_name not in self._validators:
            self._validators[tool_name] = []
        self._validators[tool_name].append(validator)
        
        # Also register with the validator registry
        self._validator_registry.register(validator)

    def get(self, name: str) -> Optional[ToolFn]:
        """Get tool function by name"""
        return self._tools.get(name)
    
    def get_spec(self, name: str) -> Optional['ToolSpec']:
        """Get full ToolSpec by name"""
        return self._specs.get(name)
    
    def get_policy(self, name: str) -> Optional['Policy']:
        """Get validation policy for a tool"""
        return self._policies.get(name)
    
    def get_validators(self, name: str) -> List:
        """Get validators for a tool"""
        return self._validators.get(name, [])
    
    def get_validation_engine(self, tool_name: str) -> Optional['ValidationEngine']:
        """
        Get validation engine configured for a specific tool.
        
        Args:
            tool_name: Tool name
            
        Returns:
            ValidationEngine instance or None if no policy exists
        """
        policy = self._policies.get(tool_name)
        if not policy:
            return None
            
        # Create engine with tool-specific policy
        from ..validate import ValidationEngine
        return ValidationEngine(
            registry=self._validator_registry,
            policy=policy,
            strict_mode=False
        )
    
    def list(self) -> list[str]:
        return list(self._tools.keys())
    
    def describe(self, name: str) -> Dict[str, Any]:

        fn = self._tools.get(name)
        if fn is None:
            return {}
        
        result = {
            "name": name,
            "doc": fn.__doc__ or "",
            "callable": str(fn)
        }
        
        # Add metadata if available
        spec = self._specs.get(name)
        if spec:
            result["risk_level"] = spec.tool_metadata.risk_level.value
            result["side_effect"] = spec.tool_metadata.side_effect.value
            result["default_action"] = spec.tool_metadata.default_action.value
            result["strict_required"] = spec.tool_metadata.strict_required
        
        # Add validator counts
        policy = self._policies.get(name)
        validators = self._validators.get(name, [])
        result["policy_enabled"] = policy is not None
        result["validators_count"] = len(validators)
        
        if policy:
            enabled_validators = policy.get_enabled_validators()
            result["enabled_validators_count"] = len(enabled_validators)
        
        return result



