# failcore/adapters/integrations/langchain/wrapper.py
"""
LangChain BaseTool wrapper - optional facade for Agent compatibility.

This is ONLY a facade layer for LangChain Agent integration.
All execution still goes through FailCore's Invoker.

Philosophy:
- This is integration sugar, not core execution model
- Execution sovereignty belongs to FailCore Invoker
- This wrapper only provides shape compatibility
- Delayed binding: tool references by name, resolved at runtime from active context

Architecture:
- bind_context=False (default): Tool can be reused across multiple run() contexts
- bind_context=True: Tool is pinned to creation-time context (strict isolation)
- All errors use FailCoreError with proper error codes (no magic exceptions)
- Full async support: async agents work via ctx.acall() (no user changes needed)

"""

from typing import Any, Callable, Optional
from functools import wraps
import inspect

try:
    from langchain_core.tools import BaseTool
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseTool = None
    _LANGCHAIN_AVAILABLE = False


def to_langchain_tool(
    tool_name: str,
    description: str = "",
    bind_context: bool = False,
) -> Any:
    """
    Wrap FailCore-registered tool as LangChain BaseTool (optional facade).
    
    Philosophy:
    - Execution sovereignty belongs to FailCore Invoker
    - This is a facade layer for Agent compatibility only
    - References tool by name (most stable identifier)
    - Supports delayed binding: tool can be created once and used across multiple run() contexts
    
    Use Case:
    - LangChain Agent requires BaseTool instances in agent.tools
    - You want FailCore protection but need Agent compatibility
    
    Important:
    - This is a facade layer, not the main execution path
    - All calls still go through ctx.call() → Invoker.invoke()
    - The tool must be registered in RunContext first (via guard())
    
    Args:
        tool_name: Tool name (must be registered via guard())
        description: Tool description (optional, for Agent display)
        bind_context: If True, bind to creation-time context and reject cross-context calls.
                     If False (default), only require *any* active context (flexible reuse).
    
    Returns:
        BaseTool instance for LangChain Agent
    
    Example (Recommended - Create inside run()):
        >>> from failcore import run, guard
        >>> from failcore.adapters.langchain import guard_tool
        >>> 
        >>> with run(policy="fs_safe") as ctx:
        ...     # Register tool first
        ...     guard(write_file, risk="high", effect="fs")
        ...     
        ...     # Create facade AFTER registration (recommended)
        ...     lc_tool = guard_tool("write_file", description="Write files")
        ...     agent = create_agent(tools=[lc_tool])
        ...     agent.invoke(...)  # ✅ Works with full schema support
    
    Example (Advanced - Reuse across runs):
        >>> # ⚠️ Creating outside run() loses parameter schema
        >>> # This works but AI agents can't see parameter types
        >>> lc_tool = guard_tool("write_file", description="Write files")
        >>> 
        >>> with run(policy="fs_safe") as ctx:
        ...     guard(write_file, risk="high", effect="fs")
        ...     agent = create_agent(tools=[lc_tool])
        ...     agent.invoke(...)  # ⚠️ Works but without schema hints
    
    Example (Strict Mode - bind_context=True):
        >>> with run(policy="fs_safe") as ctx:
        ...     guard(write_file, risk="high", effect="fs")
        ...     lc_tool = guard_tool("write_file", bind_context=True)
        ...     agent = create_agent(tools=[lc_tool])
        ...     agent.invoke(...)  # ✅ Works
        >>> 
        >>> with run(policy="fs_safe") as ctx2:
        ...     guard(write_file, risk="high", effect="fs")
        ...     agent2 = create_agent(tools=[lc_tool])
        ...     agent2.invoke(...)  # ❌ FailCoreError: CONTEXT_MISMATCH
    
    Best Practices:
        - ✅ **Recommended**: Create guard_tool() INSIDE run() after guard() registration
          → Full parameter schema support for AI agents
          → LangChain can validate and auto-complete parameters
        
        - ⚠️ **Advanced**: Create guard_tool() OUTSIDE run() for reuse
          → Works but loses parameter schema (AI agents fly blind)
          → Use only if you control parameter passing explicitly
        
        - bind_context=False: Tool reusable across runs (default, flexible)
        - bind_context=True: Tool pinned to creation context (strict isolation)
    """
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "langchain-core not installed. "
            "Install with: pip install failcore[langchain]"
        )
    
    from langchain_core.tools import StructuredTool
    from failcore.api.context import get_current_context
    from failcore.core.errors import FailCoreError
    from failcore.core.errors import codes
    
    # Capture creation-time context if bind_context=True
    bound_context_id = None
    if bind_context:
        creation_ctx = get_current_context()
        if creation_ctx is not None:
            bound_context_id = id(creation_ctx)
    
    def failcore_guarded_fn(**kwargs):
        """
        Execution wrapper that goes through FailCore's Invoker.
        
        This ensures all security checks, policy enforcement,
        and tracing happens properly.
        
        Context binding:
        - bind_context=False: Only requires *any* active context (flexible reuse)
        - bind_context=True: Requires the *same* context as creation time (strict isolation)
        
        """
        ctx = get_current_context()
        
        # Error 1: No active context at all
        if ctx is None:
            raise FailCoreError(
                message=(
                    f"Tool '{tool_name}' requires active run() context.\n"
                    f"Wrap your code with:\n"
                    f"  with run(policy='safe') as ctx:\n"
                    f"      agent = create_agent(tools=[tool])\n"
                    f"      agent.invoke(...)"
                ),
                error_code=codes.PRECONDITION_FAILED,
                error_type="CONTEXT_ERROR",
                phase="execute",
                retryable=False,
                details={
                    "tool_name": tool_name,
                    "reason": "no_active_context",
                    "hint": "Call within run() block"
                }
            )
        
        # Error 2: Context mismatch (only if bind_context=True)
        if bind_context and bound_context_id is not None:
            current_context_id = id(ctx)
            if current_context_id != bound_context_id:
                raise FailCoreError(
                    message=(
                        f"Tool '{tool_name}' was bound to a different run() context.\n"
                        f"This tool was created with bind_context=True and cannot be reused across runs.\n"
                        f"Either:\n"
                        f"  1. Create tool inside each run() block, or\n"
                        f"  2. Use bind_context=False (default) for cross-run reuse"
                    ),
                    error_code=codes.PRECONDITION_FAILED,
                    error_type="CONTEXT_ERROR",
                    phase="execute",
                    retryable=False,
                    details={
                        "tool_name": tool_name,
                        "reason": "context_mismatch",
                        "bound_context_id": bound_context_id,
                        "current_context_id": current_context_id,
                        "hint": "Use bind_context=False for tool reuse"
                    }
                )
        
        # Error 3: Tool not registered in current context
        if ctx._tools.get(tool_name) is None:
            registered_tools = ctx._tools.list()
            raise FailCoreError(
                message=(
                    f"Tool '{tool_name}' not registered in current run() context.\n"
                    f"Register it first with guard():\n"
                    f"  safe_tool = guard(your_tool, risk='high', effect='fs')\n"
                    f"\n"
                    f"Registered tools in this context: {registered_tools}"
                ),
                error_code=codes.TOOL_NOT_FOUND,
                error_type="REGISTRY_ERROR",
                phase="execute",
                retryable=False,
                details={
                    "tool_name": tool_name,
                    "registered_tools": registered_tools,
                    "context_id": id(ctx)
                }
            )
        
        # Execute through FailCore's Invoker
        # This is the ONLY execution path - no backdoors
        return ctx.call(tool_name, **kwargs)
    
    async def failcore_guarded_fn_async(**kwargs):
        """
        Async execution wrapper that goes through FailCore's Invoker.
        
        Routes to ctx.acall() for async-compatible execution.
        """
        ctx = get_current_context()
        
        # Same validation as sync version
        if ctx is None:
            raise FailCoreError(
                message=(
                    f"Tool '{tool_name}' requires active run() context.\n"
                    f"Wrap your code with:\n"
                    f"  with run(policy='safe') as ctx:\n"
                    f"      agent = create_agent(tools=[tool])\n"
                    f"      await agent.ainvoke(...)"
                ),
                error_code=codes.PRECONDITION_FAILED,
                error_type="CONTEXT_ERROR",
                phase="execute",
                retryable=False,
                details={
                    "tool_name": tool_name,
                    "reason": "no_active_context",
                    "hint": "Call within run() block"
                }
            )
        
        if bind_context and bound_context_id is not None:
            current_context_id = id(ctx)
            if current_context_id != bound_context_id:
                raise FailCoreError(
                    message=(
                        f"Tool '{tool_name}' was bound to a different run() context.\n"
                        f"This tool was created with bind_context=True and cannot be reused across runs.\n"
                        f"Either:\n"
                        f"  1. Create tool inside each run() block, or\n"
                        f"  2. Use bind_context=False (default) for cross-run reuse"
                    ),
                    error_code=codes.PRECONDITION_FAILED,
                    error_type="CONTEXT_ERROR",
                    phase="execute",
                    retryable=False,
                    details={
                        "tool_name": tool_name,
                        "reason": "context_mismatch",
                        "bound_context_id": bound_context_id,
                        "current_context_id": current_context_id,
                        "hint": "Use bind_context=False for tool reuse"
                    }
                )
        
        if ctx._tools.get(tool_name) is None:
            registered_tools = ctx._tools.list()
            raise FailCoreError(
                message=(
                    f"Tool '{tool_name}' not registered in current run() context.\n"
                    f"Register it first with guard():\n"
                    f"  safe_tool = guard(your_tool, risk='high', effect='fs')\n"
                    f"\n"
                    f"Registered tools in this context: {registered_tools}"
                ),
                error_code=codes.TOOL_NOT_FOUND,
                error_type="REGISTRY_ERROR",
                phase="execute",
                retryable=False,
                details={
                    "tool_name": tool_name,
                    "registered_tools": registered_tools,
                    "context_id": id(ctx)
                }
            )
        
        # Execute through FailCore's async Invoker
        return await ctx.acall(tool_name, **kwargs)
    
    # Helper to dynamically get tool function at runtime
    def get_tool_fn():
        """Get tool function from current context (dynamic lookup)"""
        ctx = get_current_context()
        if ctx is not None:
            return ctx._tools.get(tool_name)
        return None
    
    # Create wrapper that dynamically adapts to the tool's signature
    def dynamic_wrapper(*args, **kwargs):
        """Wrapper that uses the actual tool's signature if available"""
        # LangChain passes tool input as first positional arg (dict) for StructuredTool
        # Need to unpack it into kwargs
        if args and len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            # LangChain style: single dict argument
            kwargs = args[0]
            args = ()
        
        tool_fn = get_tool_fn()
        if tool_fn is not None and callable(tool_fn) and args:
            # Convert positional args to kwargs using the real tool's signature
            sig = inspect.signature(tool_fn)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return failcore_guarded_fn(**bound.arguments)
        else:
            # No positional args or no tool found yet - pass through
            return failcore_guarded_fn(*args, **kwargs)
    
    async def dynamic_async_wrapper(*args, **kwargs):
        """Async wrapper that uses the actual tool's signature if available"""
        # LangChain passes tool input as first positional arg (dict) for StructuredTool
        # Need to unpack it into kwargs
        if args and len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            # LangChain style: single dict argument
            kwargs = args[0]
            args = ()
        
        tool_fn = get_tool_fn()
        if tool_fn is not None and callable(tool_fn) and args:
            # Convert positional args to kwargs using the real tool's signature
            sig = inspect.signature(tool_fn)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return await failcore_guarded_fn_async(**bound.arguments)
        else:
            # No positional args or no tool found yet - pass through
            return await failcore_guarded_fn_async(*args, **kwargs)
    
    # Try to get tool function for signature inference (if available at creation time)
    tool_fn_for_schema = get_tool_fn()
    
    # Warn if tool not available (created outside run() context)
    if tool_fn_for_schema is None:
        import warnings
        warnings.warn(
            f"guard_tool('{tool_name}') created outside run() context or before tool registration.\n"
            f"This works but loses parameter schema - AI agents can't see parameter types.\n"
            f"Recommendation: Create guard_tool() INSIDE run() AFTER guard() registration:\n"
            f"  with run(...) as ctx:\n"
            f"      guard(your_tool, ...)\n"
            f"      lc_tool = guard_tool('{tool_name}')",
            UserWarning,
            stacklevel=2
        )
    
    # Create LangChain StructuredTool with both sync and async support
    if tool_fn_for_schema is not None and callable(tool_fn_for_schema):
        # Tool available at creation time - use its signature for schema inference
        @wraps(tool_fn_for_schema)
        def schema_wrapper(*args, **kwargs):
            return dynamic_wrapper(*args, **kwargs)
        
        @wraps(tool_fn_for_schema)
        async def async_schema_wrapper(*args, **kwargs):
            return await dynamic_async_wrapper(*args, **kwargs)
        
        lc_tool = StructuredTool.from_function(
            func=schema_wrapper,
            name=tool_name,
            description=description or f"FailCore-protected tool: {tool_name}",
            coroutine=async_schema_wrapper,
        )
    else:
        # Tool not available yet - create wrapper with **kwargs to accept any params
        # We need to bypass LangChain's schema inference by using infer_schema=False
        def schema_resolving_wrapper(**kwargs):
            """Generic wrapper that accepts any keyword arguments"""
            return dynamic_wrapper(**kwargs)
        
        async def async_schema_resolving_wrapper(**kwargs):
            """Async generic wrapper that accepts any keyword arguments"""
            return await dynamic_async_wrapper(**kwargs)
        
        # Create StructuredTool without schema inference
        # This tells LangChain to pass parameters directly without validation
        try:
            lc_tool = StructuredTool.from_function(
                func=schema_resolving_wrapper,
                name=tool_name,
                description=description or f"FailCore-protected tool: {tool_name}",
                coroutine=async_schema_resolving_wrapper,
                infer_schema=False,  # Don't infer schema - accept any params
            )
        except TypeError:
            # Older LangChain version doesn't support infer_schema parameter
            # Fall back to creating StructuredTool directly
            lc_tool = StructuredTool(
                name=tool_name,
                description=description or f"FailCore-protected tool: {tool_name}",
                func=schema_resolving_wrapper,
                coroutine=async_schema_resolving_wrapper,
            )
    
    # Store metadata for debugging
    lc_tool._failcore_metadata = {
        "bind_context": bind_context,
        "bound_context_id": bound_context_id,
        "tool_name": tool_name,
    }
    
    return lc_tool


# Public alias - cleaner name for external API
guard_tool = to_langchain_tool


__all__ = [
    "to_langchain_tool",  # Internal name (kept for compatibility)
    "guard_tool",         # Public API (recommended)
]
