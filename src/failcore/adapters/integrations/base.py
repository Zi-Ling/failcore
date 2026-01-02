# failcore/adapters/base.py
"""
Base Adapter - Framework-agnostic adapter infrastructure

This module provides the base infrastructure for creating adapters for any framework.
Adapters are thin translation layers that convert framework-specific tools to ToolSpec.

Philosophy:
- Adapter = Translator (not Executor)
- Execution stays in FailCore core (ToolInvoker)
- Framework-specific code is isolated in adapter modules
"""

from abc import ABC, abstractmethod
from typing import Any
from failcore.core.tools.spec import ToolSpec
from failcore.core.tools.invoker import ToolInvoker
from failcore.api.session import Session


class BaseAdapter(ABC):
    """
    Base class for framework adapters
    
    All framework adapters should inherit from this class and implement
    the translation logic from framework-specific tools to ToolSpec.
    
    Execution is delegated to FailCore's ToolInvoker - adapters do NOT
    implement execution logic.
    
    Example:
        >>> class MyFrameworkAdapter(BaseAdapter):
        ...     def translate_tool(self, tool):
        ...         return ToolSpec(name=tool.name, fn=tool.fn)
        >>> 
        >>> adapter = MyFrameworkAdapter(session)
        >>> adapter.register_tool(my_framework_tool)
        >>> result = adapter.invoke("tool_name", x=5)
    """
    
    def __init__(self, session: Session):
        """
        Create an adapter for a FailCore session
        
        Args:
            session: FailCore session (provides invoker, validator, policy, trace)
        """
        self.session = session
        self.invoker = session.invoker
    
    @abstractmethod
    def translate_tool(self, tool: Any) -> ToolSpec:
        """
        Translate framework-specific tool to ToolSpec
        
        This is the ONLY method that needs to be implemented by subclasses.
        All execution logic is handled by FailCore core.
        
        Args:
            tool: Framework-specific tool object
        
        Returns:
            ToolSpec: Framework-agnostic tool specification
        
        Example:
            >>> def translate_tool(self, tool):
            ...     return ToolSpec(
            ...         name=tool.name,
            ...         fn=tool.execute,
            ...         description=tool.description
            ...     )
        """
        pass
    
    def register_tool(self, tool: Any):
        """
        Register a framework-specific tool
        
        Args:
            tool: Framework-specific tool object
        """
        # Translate to ToolSpec
        spec = self.translate_tool(tool)
        
        # Register with invoker
        self.invoker.register_spec(spec)
    
    def invoke(self, tool_name: str, **params) -> Any:
        """
        Invoke a tool (delegates to FailCore invoker)
        
        Args:
            tool_name: Tool name
            **params: Tool parameters
        
        Returns:
            StepResult: FailCore execution result
        """
        return self.invoker.invoke(tool_name, **params)


__all__ = ["BaseAdapter"]
