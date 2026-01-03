# failcore/adapters/langchain/mapper.py
"""
LangChain Tool Translator - Convert LangChain tools to ToolSpec

This is a pure translation module with ZERO execution logic.
It only knows how to read LangChain tool structures and convert them to ToolSpec.
"""

from typing import Any
try:
    from langchain_core.tools import BaseTool
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseTool = None
    _LANGCHAIN_AVAILABLE = False

from failcore.core.tools.spec import ToolSpec


def map_tool(tool: Any) -> ToolSpec:
    """
    Convert LangChain tool to ToolSpec (pure translation, no execution)
    
    Args:
        tool: LangChain tool (BaseTool, @tool decorated function, etc.)
    
    Returns:
        ToolSpec: Framework-agnostic tool specification
    
    Example:
        >>> from langchain_core.tools import tool
        >>> @tool
        ... def my_tool(x: int) -> int:
        ...     return x * 2
        >>> schemas = langchain_tool_to_spec(my_tool)
        >>> print(schemas.name, schemas.fn)
    """
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain-core not installed. "
            "Install with: pip install failcore[langchain]"
        )
    
    # Handle @tool decorated functions
    if hasattr(tool, 'name') and hasattr(tool, 'func'):
        return ToolSpec(
            name=tool.name,
            fn=tool.func,
            description=tool.description or "",
            schema=None,
            policy_tags=[],
            extras={"source": "langchain", "type": "tool_decorator"}
        )
    
    # Handle BaseTool instances
    if BaseTool and isinstance(tool, BaseTool):
        return ToolSpec(
            name=tool.name,
            fn=tool._run,
            description=tool.description or "",
            schema=None,
            policy_tags=[],
            extras={"source": "langchain", "type": "BaseTool"}
        )
    
    # Fallback: treat as callable
    tool_name = getattr(tool, '__name__', 'unknown_tool')
    return ToolSpec(
        name=tool_name,
        fn=tool,
        description=tool.__doc__ or "",
        schema=None,
        policy_tags=[],
        extras={"source": "langchain", "type": "callable"}
    )


__all__ = ["langchain_tool_to_spec"]
