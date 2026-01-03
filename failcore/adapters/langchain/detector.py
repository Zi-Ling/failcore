# failcore/adapters/integrations/langchain/detector.py
"""
LangChain type detector - identify LangChain tools and structures.
"""

from typing import Any


def is_langchain_available() -> bool:
    """Check if langchain-core is installed."""
    try:
        import langchain_core.tools
        return True
    except ImportError:
        return False


def is_langchain_tool(obj: Any) -> bool:
    """
    Check if object is a LangChain tool (BaseTool or @tool decorated).
    
    Args:
        obj: Object to check
    
    Returns:
        True if object is a LangChain tool
    """
    if not is_langchain_available():
        return False
    
    try:
        from langchain_core.tools import BaseTool
        
        # Check BaseTool instances
        if isinstance(obj, BaseTool):
            return True
        
        # Check @tool decorated functions (StructuredTool)
        if hasattr(obj, 'name') and hasattr(obj, 'func') and hasattr(obj, 'invoke'):
            return True
        
    except ImportError:
        pass
    
    return False


def get_langchain_tool_type(obj: Any) -> str:
    """
    Get specific type of LangChain tool.
    
    Args:
        obj: LangChain tool object
    
    Returns:
        Tool type string: "BaseTool", "StructuredTool", or "unknown"
    """
    if not is_langchain_tool(obj):
        return "unknown"
    
    # Check specific types
    if hasattr(obj, '__class__'):
        class_name = obj.__class__.__name__
        if 'StructuredTool' in class_name:
            return "StructuredTool"
        if 'Tool' in class_name:
            return "BaseTool"
    
    return "unknown"


__all__ = [
    "is_langchain_available",
    "is_langchain_tool",
    "get_langchain_tool_type",
]
