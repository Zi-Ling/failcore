# failcore/core/tools/invoker.py
"""
Tool Invoker - Framework-agnostic tool execution engine

The invoker is responsible for:
1. Validate → Call → Trace → Normalize result
2. Enforcing policy and validation rules
3. Recording execution traces
4. Handling errors uniformly

This is the ONLY entry point for tool execution in FailCore.
Adapters should NEVER implement their own execution logic.
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING
from ..step import Step, StepResult, RunContext
from .spec import ToolSpec

if TYPE_CHECKING:
    from ..executor.executor import Executor


class ToolInvoker:
    """
    Unified tool execution engine (framework-agnostic)
    
    This is the core execution layer. All adapters should use this invoker
    instead of implementing their own execution logic.
    
    Responsibilities:
    - Validate inputs (preconditions)
    - Execute tool
    - Enforce policy
    - Record trace
    - Normalize output (postconditions)
    
    Example:
        >>> invoker = ToolInvoker(executor, context)
        >>> result = invoker.invoke("read_file", path="data.txt")
    """
    
    def __init__(self, executor: Executor, context: RunContext):
        """
        Create a tool invoker
        
        Args:
            executor: Core executor (handles validation, policy, trace)
            context: Run context (run_id, sandbox, tags)
        """
        self._executor = executor
        self._context = context
        self._step_counter = 0
    
    def invoke(self, tool_name: str, **params) -> StepResult:
        """
        Invoke a tool by name with parameters
        
        This is the ONLY way to execute a tool in FailCore.
        
        Args:
            tool_name: Tool name (must be registered)
            **params: Tool parameters
        
        Returns:
            StepResult: Execution result (status, output, error, etc.)
        
        Example:
            >>> result = invoker.invoke("divide", a=6, b=2)
            >>> print(result.status, result.output.value)
        """
        # Generate step ID
        self._step_counter += 1
        step_id = f"s{self._step_counter:04d}"
        
        # Create step
        step = Step(
            id=step_id,
            tool=tool_name,
            params=params
        )
        
        # Execute through core executor
        # This handles: validation → policy → execution → trace → normalization
        return self._executor.execute(step, self._context)
    
    def register_spec(self, spec: ToolSpec):
        """
        Register a tool from a ToolSpec
        
        This is the framework-agnostic way to register tools.
        Adapters should convert framework-specific tools to ToolSpec,
        then call this method.
        
        Args:
            spec: Tool specification
        
        Example:
            >>> schemas = ToolSpec(name="divide", fn=lambda a, b: a / b)
            >>> invoker.register_spec(schemas)
        """
        self._executor.tools.register(spec.name, spec.fn)
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is registered"""
        return self._executor.tools.get(tool_name) is not None


__all__ = ["ToolInvoker"]
