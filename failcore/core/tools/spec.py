# failcore/core/tools/spec.py
"""
Tool Specification - Framework-agnostic tool definition
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, List


@dataclass
class ToolSpec:
    """
    Framework-agnostic tool specification
    
    This is the unified representation of a tool, regardless of the source
    (native Python function, LangChain tool, LlamaIndex tool, etc.)
    
    Attributes:
        name: Tool name (unique identifier)
        fn: Callable function to execute
        description: Human-readable description
        schema: Optional JSON schema for parameters
        policy_tags: Optional policy tags (e.g., ["filesystem", "network", "dangerous"])
        metadata: Optional metadata (framework-specific info, etc.)
    """
    name: str
    fn: Callable[..., Any]
    description: str = ""
    schema: Optional[Dict[str, Any]] = None
    policy_tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def invoke(self, **params) -> Any:
        """
        Invoke the tool with parameters
        
        Args:
            **params: Tool parameters
        
        Returns:
            Tool execution result
        """
        return self.fn(**params)


__all__ = ["ToolSpec"]
