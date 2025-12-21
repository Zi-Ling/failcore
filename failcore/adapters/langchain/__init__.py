# /failcore/adapters/langchain/__init__.py
"""
LangChain Adapter - Thin translation layer

This adapter ONLY translates LangChain tools to FailCore's ToolSpec.
Execution is handled by FailCore core, not by this adapter.

Philosophy:
- Adapter = Translator (not Executor)
- Execution stays in FailCore core
- LangChain-specific code isolated here

Usage:
    from failcore import Session, presets
    from failcore.adapters.langchain import langchain_tool_to_spec
    from langchain_core.tools import tool
    
    @tool
    def my_tool(x: int) -> int:
        return x * 2
    
    session = Session(validator=presets.fs_safe())
    spec = langchain_tool_to_spec(my_tool)
    session.invoker.register_spec(spec)
    result = session.invoker.invoke("my_tool", x=5)
"""

from .mapper import map_langchain_tool

__all__ = [
    "map_langchain_tool",
]