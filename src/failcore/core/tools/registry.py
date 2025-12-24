# \failcore\core\tools\registry.py

from typing import Callable, Dict, Optional, Any, List
import os

# ---------------------------
# Tool Registry
# ---------------------------

ToolFn = Callable[..., Any]


class ToolRegistry:
    """
    Enhanced tool registry with metadata and auto-rule assembly
    
    Features:
    - Tool metadata tracking (risk_level, side_effect, default_policy)
    - Automatic validation rule assembly based on metadata
    - Strict mode enforcement for HIGH risk tools
    - Precondition/Postcondition validator registration
    """
    def __init__(self, sandbox_root: Optional[str] = None) -> None:
        """
        Initialize tool registry
        
        Args:
            sandbox_root: Sandbox root directory for path validation
        """
        from .spec import ToolSpec
        from ..validate import RuleAssembler, ValidationRuleSet, ValidationPreset
        
        self._tools: Dict[str, ToolFn] = {}
        self._specs: Dict[str, ToolSpec] = {}  # Store full ToolSpec
        self._preconditions: Dict[str, List] = {}  # tool_name -> [validators]
        self._postconditions: Dict[str, List] = {}  # tool_name -> [validators]
        self._presets: Dict[str, ValidationPreset] = {}  # tool_name -> preset
        
        # Rule assembler for automatic validation
        self.sandbox_root = sandbox_root or os.getcwd()
        self._rule_assembler = RuleAssembler(sandbox_root=self.sandbox_root)

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
        preset: Optional['ValidationPreset'] = None,
        auto_assemble: bool = True,
    ) -> None:
        """
        Register a tool with full metadata and validation      
        Args:
            spec: ToolSpec with metadata
            preset: Optional validation preset
            auto_assemble: Auto-assemble validation rules based on metadata
            
        Raises:
            ValueError: If HIGH risk tool lacks strict validation
        """
        from .metadata import validate_metadata_runtime, RiskLevel
        from ..validate.rules import ValidationRuleSet
        
        name = spec.name
        
        # Validate metadata constraints
        # Consider strict mode enabled if: preset provided OR auto_assemble will add validators
        has_strict = preset is not None or auto_assemble
        
        try:
            validate_metadata_runtime(spec.tool_metadata, strict_enabled=has_strict)
        except ValueError as e:
            raise ValueError(f"Tool '{name}' metadata validation failed: {e}")
        
        # Store tool and spec
        self._tools[name] = spec.fn
        self._specs[name] = spec
        
        # Store preset if provided
        if preset:
            self._presets[name] = preset
            rules = preset.to_rule_set()
            self._preconditions[name] = rules.preconditions
            self._postconditions[name] = rules.postconditions
        
        # Auto-assemble validation rules if enabled
        elif auto_assemble:
            rules = self._rule_assembler.assemble(
                tool_metadata=spec.tool_metadata,
                output_contract=spec.extras.get("output_contract"),
                path_param_names=spec.extras.get("path_params"),
                network_param_names=spec.extras.get("network_params"),
                network_allowlist=spec.extras.get("network_allowlist"),
            )
            
            if not rules.is_empty():
                self._preconditions[name] = rules.preconditions
                self._postconditions[name] = rules.postconditions
        
        # For HIGH risk tools without validation, raise error
        if spec.tool_metadata.risk_level == RiskLevel.HIGH:
            if name not in self._preconditions and name not in self._postconditions:
                if not has_strict:
                    raise ValueError(
                        f"HIGH risk tool '{name}' must have strict validation. "
                        f"Either provide a preset or enable auto_assemble with proper metadata."
                    )
    
    def register_precondition(self, tool_name: str, validator) -> None:
        """
        Register precondition validator for a tool    
        Args:
            tool_name: Tool name
            validator: PreconditionValidator instance
        """
        if tool_name not in self._preconditions:
            self._preconditions[tool_name] = []
        self._preconditions[tool_name].append(validator)
    
    def register_postcondition(self, tool_name: str, validator) -> None:
        """
        Register postcondition validator for a tool
        Args:
            tool_name: Tool name
            validator: PostconditionValidator instance
        """
        if tool_name not in self._postconditions:
            self._postconditions[tool_name] = []
        self._postconditions[tool_name].append(validator)

    def get(self, name: str) -> Optional[ToolFn]:
        """Get tool function by name"""
        return self._tools.get(name)
    
    def get_spec(self, name: str) -> Optional['ToolSpec']:
        """Get full ToolSpec by name"""
        return self._specs.get(name)
    
    def get_preconditions(self, name: str) -> List:
        """Get precondition validators for a tool"""
        return self._preconditions.get(name, [])
    
    def get_postconditions(self, name: str) -> List:
        """Get postcondition validators for a tool"""
        return self._postconditions.get(name, [])
    
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
            result["default_policy"] = spec.tool_metadata.default_policy.value
            result["strict_required"] = spec.tool_metadata.strict_required
        
        # Add validator counts
        result["preconditions_count"] = len(self._preconditions.get(name, []))
        result["postconditions_count"] = len(self._postconditions.get(name, []))
        
        return result



