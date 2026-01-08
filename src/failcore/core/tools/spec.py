# failcore/core/tools/spec.py
"""
Tool Specification - framework-agnostic tool definition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .metadata import ToolMetadata


@dataclass
class ToolSpec:
    """
    Framework-agnostic tool specification.

    This is the unified representation of a tool, regardless of the source
    (native Python function, LangChain tool, LlamaIndex tool, etc.).
    """

    name: str
    fn: Callable[..., Any]

    description: str = ""
    schema: Optional[Dict[str, Any]] = None

    policy_tags: List[str] = field(default_factory=list)

    # Arbitrary non-security extra metadata (source framework, adapter hints, etc.)
    extras: Dict[str, Any] = field(default_factory=dict)

    # Security/policy metadata (required)
    tool_metadata: ToolMetadata = field(default_factory=lambda: ToolMetadata(
        # safe default: medium/read/warn
        risk_level="medium",   # type: ignore[arg-type]
        side_effect="read",    # type: ignore[arg-type]
        default_action="warn", # type: ignore[arg-type]
    ))

    def invoke(self, **params: Any) -> Any:
        return self.fn(**params)


__all__ = ["ToolSpec"]
