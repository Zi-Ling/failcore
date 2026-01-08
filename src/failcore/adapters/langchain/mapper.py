# failcore/adapters/integrations/langchain/mapper.py
"""
LangChain Tool Mapper - Convert LangChain tools to ToolSpec.

This is a pure translation module with ZERO execution logic.
It only reads LangChain tool structures and converts them to ToolSpec.

CRITICAL: All execution must go through FailCore's Invoker, not LangChain's _run().
"""

from typing import Any, Dict
from functools import wraps

try:
    from langchain_core.tools import BaseTool
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseTool = None
    _LANGCHAIN_AVAILABLE = False

from failcore.core.tools.spec import ToolSpec
from failcore.core.tools.metadata import ToolMetadata


def _create_invoke_wrapper(tool: Any):
    """
    Create a wrapper that calls tool.invoke() instead of tool._run().
    
    This ensures we use LangChain's public API, which handles:
    - Argument validation
    - Error handling
    - Async/sync conversion
    
    Args:
        tool: LangChain tool object
    
    Returns:
        Callable that invokes the tool through public API
    """
    @wraps(tool.invoke)
    def wrapper(**kwargs):
        # LangChain's tool.invoke() expects 'input' parameter (dict or str)
        # Pass kwargs as the input dict
        return tool.invoke(input=kwargs)
    
    return wrapper


def map_langchain_tool(
    tool: Any,
    risk: str = "medium",
    effect: str = None,
    action: str = "warn",
) -> ToolSpec:
    """
    Convert LangChain tool to ToolSpec (pure translation, no execution).
    
    Philosophy:
    - Extract metadata from LangChain tool
    - Create wrapper that calls tool.invoke() (public API)
    - Return ToolSpec for FailCore's Invoker to execute
    
    Args:
        tool: LangChain tool (BaseTool, @tool decorated function, etc.)
        risk: Risk level ("low", "medium", "high")
        effect: Side effect type (None, "fs", "net", "exec", "process")
        action: Default action ("allow", "warn", "block")
    
    Returns:
        ToolSpec: Framework-agnostic tool specification
    
    Example:
        >>> from langchain_core.tools import tool
        >>> @tool
        ... def my_tool(x: int) -> int:
        ...     '''Multiply by 2'''
        ...     return x * 2
        >>> spec = map_langchain_tool(my_tool, risk="low", effect="read")
        >>> print(spec.name, spec.description)
        my_tool Multiply by 2
    """
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain-core not installed. "
            "Install with: pip install failcore[langchain]"
        )
    
    # Import mapping utilities
    from failcore.api.guard import _map_risk_level, _map_side_effect, _map_default_action
    
    # Extract metadata from LangChain tool
    tool_name = getattr(tool, 'name', getattr(tool, '__name__', 'unknown_tool'))
    tool_desc = getattr(tool, 'description', tool.__doc__ or "")
    
    # Determine tool type and create appropriate wrapper
    extras: Dict[str, Any] = {"source": "langchain"}
    
    # Handle @tool decorated functions (StructuredTool)
    if hasattr(tool, 'name') and hasattr(tool, 'func') and hasattr(tool, 'invoke'):
        extras["type"] = "StructuredTool"
        fn = _create_invoke_wrapper(tool)
    
    # Handle BaseTool instances
    elif BaseTool and isinstance(tool, BaseTool):
        extras["type"] = "BaseTool"
        fn = _create_invoke_wrapper(tool)
    
    # Fallback: treat as callable
    else:
        extras["type"] = "callable"
        fn = tool
    
    # Build security metadata
    metadata = ToolMetadata(
        risk_level=_map_risk_level(risk),
        side_effect=_map_side_effect(effect) if effect else None,
        default_action=_map_default_action(action),
    )
    
    return ToolSpec(
        name=tool_name,
        fn=fn,
        description=tool_desc,
        schema=None,  # TODO: Extract from args_schema if available
        policy_tags=[],
        extras=extras,
        tool_metadata=metadata,
    )


__all__ = ["map_langchain_tool"]
