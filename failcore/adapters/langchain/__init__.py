# failcore/adapters/integrations/langchain/__init__.py
"""
LangChain integration for FailCore - Core Gateway Architecture

Architecture:
- Main path: guard() auto-detects LangChain tools → maps to ToolSpec → executes via Invoker
- Optional path: guard_tool() wraps FailCore tools as BaseTool for Agent compatibility
- All execution flows through FailCore's Invoker - single execution gateway

Philosophy:
- Execution sovereignty belongs to FailCore Invoker (not LangChain internals)
- LangChain tools are just another input format (like native Python functions)
- Adapter is pure translator, not executor
- Optional facade layer for Agent compatibility

Usage (Main Path - Recommended):
    from failcore import run, guard
    from langchain_core.tools import tool
    
    @tool
    def my_tool(x: int) -> int:
        '''Multiply by 2'''
        return x * 2
    
    with run(policy="safe") as ctx:
        # guard() auto-detects and adapts LangChain tool
        safe_tool = guard(my_tool, risk="low", effect="read")
        result = safe_tool(x=5)

Usage (Optional Path - Agent Compatibility):
    from failcore import run, guard
    from failcore.adapters.langchain import guard_tool
    
    with run(policy="safe") as ctx:
        safe_tool = guard(my_tool, risk="low", effect="read")
        
        # Wrap as BaseTool for Agent
        lc_tool = guard_tool("my_tool", description="Protected tool")
        agent = create_agent(tools=[lc_tool])

Legacy Usage (Session API):
    from failcore import Session
    from failcore.adapters.integrations.langchain import map_langchain_tool
    
    session = Session(validator=presets.fs_safe())
    spec = map_langchain_tool(my_tool, risk="low", effect="read")
    session.invoker.register_spec(spec)
    result = session.invoker.invoke("my_tool", x=5)
"""

from .detector import is_langchain_tool, is_langchain_available
from .mapper import map_langchain_tool
from .wrapper import to_langchain_tool, guard_tool



__all__ = [
    # Type detection
    "is_langchain_tool",
    "is_langchain_available",
    
    # Core adapter (main path)
    "map_langchain_tool",  # Low-level mapper
    
    # Optional facade (for Agent compatibility)
    "guard_tool",         # Recommended public API
    "to_langchain_tool",  # Internal name (kept for compatibility)
]