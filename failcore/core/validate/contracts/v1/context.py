# failcore/core/validate/contracts/v1/context.py
"""
ContextV1: Platform-agnostic validation context.

This context is the input to all builtin.
It must be:
- Serializable (JSON-compatible, no runtime objects)
- Platform-agnostic (works across Python, Rust, WASM, mobile)
- Complete (contains all information needed for validation)

Design principles:
- No file handles, stack frames, or runtime-specific objects
- All platforms map their local data into this canonical form
- Extensions via the 'extra' field
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    from dataclasses import dataclass, field as Field
    BaseModel = object  # type: ignore
    ConfigDict = lambda **kwargs: None  # type: ignore


class ContextV1(BaseModel):
    """
    Platform-agnostic validation context.
    
    This is the canonical input format for all builtin.
    All platforms (SDK, Proxy, mobile, embedded) must map their
    local data into this structure.
    
    Fields:
    - tool: Tool name being validated
    - params: Tool parameters (serializable)
    - result: Tool result (for postcondition validation, optional)
    - step_id: Execution step identifier
    - state: Additional state/metadata (extensible)
    """
    model_config = ConfigDict(extra="allow")  # Allow platform-specific extensions
    
    # Core fields (required)
    tool: str = Field(description="Tool name")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool parameters (must be JSON-serializable)"
    )
    
    # Optional fields
    result: Optional[Any] = Field(
        default=None,
        description="Tool result (for postcondition validation)"
    )
    step_id: Optional[str] = Field(
        default=None,
        description="Execution step identifier"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier"
    )
    
    # Extensible state
    state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context state (platform-specific)"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Validation metadata (timestamp, trace_id, etc.)"
    )
    
    @classmethod
    def from_legacy_dict(cls, data: Dict[str, Any]) -> ContextV1:
        """
        Create ContextV1 from legacy dict context.
        
        This provides backward compatibility with existing code.
        """
        return cls(
            tool=data.get("tool", "unknown"),
            params=data.get("params", {}),
            result=data.get("result"),
            step_id=data.get("step_id"),
            state=data.get("state", {}),
            metadata=data.get("metadata", {}),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (for backward compatibility)"""
        if hasattr(self, 'model_dump'):
            return self.model_dump()
        else:
            # Fallback for non-Pydantic environments
            return {
                "tool": self.tool,
                "params": self.params,
                "result": self.result,
                "step_id": self.step_id,
                "session_id": self.session_id,
                "state": self.state,
                "metadata": self.metadata,
            }


__all__ = ["ContextV1"]
