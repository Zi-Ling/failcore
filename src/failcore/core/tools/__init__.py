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
from .registry import ToolRegistry, create_builtin_registry
from .schema import ToolSchema, ParamSchema, ParamType, SchemaRegistry, extract_schema_from_function
from .spec import ToolSpec
from .invoker import ToolInvoker


__all__ = [
    "ToolProvider",
    "ToolRegistry",
    "create_builtin_registry",
    "ToolSchema",
    "ParamSchema",
    "ParamType",
    "SchemaRegistry",
    "extract_schema_from_function",
    "ToolSpec",
    "ToolInvoker",
]