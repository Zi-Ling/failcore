# failcore/core/tools/__init__.py
"""
Core tools for Failcore.

This package defines the components responsible for:
- Providing tools
- Registering tools
- Describing tools
- Tool specification (framework-agnostic)
- Tool invocation (unified execution)

No side effects on import.
"""

from .provider import ToolProvider
from .registry import ToolRegistry
from .schema import ToolSchema, ParamSchema, ParamType, SchemaRegistry, extract_schema_from_function
from .spec import ToolSpec
from .invoker import ToolInvoker
from .metadata import ToolMetadata, RiskLevel, SideEffect, DefaultPolicy, DEFAULT_METADATA_PROFILES, validate_metadata_runtime


__all__ = [
    "ToolProvider",
    "ToolRegistry",
    "ToolSchema",
    "ParamSchema",
    "ParamType",
    "SchemaRegistry",
    "extract_schema_from_function",
    "ToolSpec",
    "ToolInvoker",
    "RiskLevel",
    "SideEffect",
    "DefaultPolicy",
    "ToolMetadata",
    "DEFAULT_METADATA_PROFILES",
    "validate_metadata_runtime",
]