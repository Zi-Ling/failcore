# failcore/api/guard.py
"""
Guard decorator - automatically inherits run context configuration
"""

from __future__ import annotations
from functools import wraps
from typing import Any, Callable, Optional, Literal, Dict, Tuple
import inspect

from .context import get_current_context


# Global cache for guarded tools: (tool_id, ctx_id) -> wrapped_callable
# This prevents duplicate registration of the same tool
_GUARD_CACHE: Dict[Tuple[int, int], Callable] = {}


# Type aliases for user-friendly API
RiskType = Literal["low", "medium", "high"]
EffectType = Literal["read", "write", "net", "exec", "process"]


def _map_risk_level(risk: str):
    """Map string risk level to RiskLevel enum"""
    from ..core.tools.metadata import RiskLevel
    
    mapping = {
        "low": RiskLevel.LOW,
        "medium": RiskLevel.MEDIUM,
        "high": RiskLevel.HIGH,
    }
    
    return mapping.get(risk.lower(), RiskLevel.MEDIUM)


def _map_side_effect(effect: str) -> Optional:
    """
    Map string effect to SideEffect enum.
    
    Returns None for unknown/unspecified effects (displayed as "unknown" in UI).
    """
    from ..core.tools.metadata import SideEffect
    
    mapping = {
        "read": SideEffect.FS,
        "write": SideEffect.FS,
        "fs": SideEffect.FS,
        "net": SideEffect.NETWORK,
        "network": SideEffect.NETWORK,
        "exec": SideEffect.EXEC,
        "process": SideEffect.PROCESS,
    }
    
    return mapping.get(effect.lower(), None)  # None = unknown


def _map_default_action(action: str):
    """Map string action to DefaultAction enum"""
    from ..core.tools.metadata import DefaultAction
    
    mapping = {
        "allow": DefaultAction.ALLOW,
        "warn": DefaultAction.WARN,
        "block": DefaultAction.BLOCK,
    }
    
    return mapping.get(action.lower(), DefaultAction.WARN)


def guard(
    fn: Optional[Callable] = None,
    *,
    risk: RiskType = "medium",
    effect: Optional[EffectType] = None,
    action: Optional[str] = None,
    description: str = "",
) -> Callable:
    """
    Guard decorator - simplified security metadata for tools.
    
    Automatically registers the decorated function with security metadata
    and executes it within the current run context.
    
    Supports:
    - Regular Python functions
    - LangChain tools (auto-detected and adapted)
    
    Args:
        fn: Function/tool to decorate (optional, supports @guard and @guard())
        risk: Risk level - "low", "medium" (default), "high"
        effect: Side effect type - None (default, shown as "unknown"), "read", "write", "fs", "net", "exec", "process"
        action: Default action - "allow", "warn" (default), "block"
        description: Tool description
    
    Simple Usage (no metadata):
        >>> from failcore import run, guard
        >>> 
        >>> with run() as ctx:
        ...     @guard
        ...     def safe_tool():
        ...         return "hello"
        ...     
        ...     result = safe_tool()
    
    With Metadata (recommended for risky operations):
        >>> with run(policy="safe") as ctx:
        ...     @guard(risk="high", effect="net")
        ...     def fetch_url(url: str):
        ...         import urllib.request
        ...         return urllib.request.urlopen(url).read()
        ...     
        ...     result = fetch_url(url="http://example.com")
    
    LangChain Integration (auto-detected):
        >>> from langchain_core.tools import tool
        >>> from failcore import run, guard
        >>> 
        >>> @tool
        ... def write_file(path: str, content: str):
        ...     '''Write content to file'''
        ...     with open(path, 'w') as f:
        ...         f.write(content)
        >>> 
        >>> with run(policy="fs_safe") as ctx:
        ...     # guard auto-detects LangChain tool and adapts it
        ...     safe_write = guard(write_file, risk="high", effect="fs")
        ...     safe_write(path="test.txt", content="hello")
    
    Metadata Defaults:
        - risk: "medium" - Most tools are medium risk
        - effect: None - Unknown/unspecified (shown as "unknown" in UI)
        - action: "warn" - Warn by default
        - policy: Inherited from run() - Usually "safe"
        - strict: Inherited from run() - Usually True
    
    Risk Levels:
        - "low": Safe operations (read-only, no network)
        - "medium": Standard operations (default)
        - "high": Dangerous operations (write files, network, system commands)
    
    Effect Types (all optional):
        - None: Unknown/unspecified (default, shown as "unknown")
        - "fs" or "read" or "write": File system operations
        - "net" or "network": Network operations
        - "exec": Local execution (shell, subprocess)
        - "process": Process lifecycle control
    
    Action Types:
        - "allow": Allow by default
        - "warn": Warn but allow (default)
        - "block": Block by default
    
    Note:
        - Must be used within a run() block
        - Automatically inherits policy/sandbox/trace from run()
        - On failure, raises FailCoreError exception
        - LangChain tools are automatically adapted to FailCore's execution model
    """
    
    def decorator(func: Callable) -> Callable:
        # Cache key: tool identity (by id) - context will be checked at runtime
        tool_id = id(func)
        
        # Get current context for eager registration
        ctx = get_current_context()
        
        # Check if this is a LangChain tool (auto-detection)
        from failcore.adapters.langchain import is_langchain_tool
        
        if is_langchain_tool(func):
            # LangChain tool detected - use mapper to convert
            from failcore.adapters.langchain import map_langchain_tool
            
            # Convert LangChain tool to ToolSpec
            tool_spec = map_langchain_tool(
                func,
                risk=risk,
                effect=effect,
                action=action or "warn",
            )
            
            # Eager registration: register tool immediately if in run() context
            if ctx is not None:
                ctx_id = id(ctx)
                cache_key = (tool_id, ctx_id)
                
                if cache_key not in _GUARD_CACHE:
                    if ctx._tools.get(tool_spec.name) is None:
                        ctx._tools.register_tool(tool_spec, auto_assemble=True)
                    _GUARD_CACHE[cache_key] = True
            
            # Create wrapper that executes through FailCore
            @wraps(tool_spec.fn)
            def langchain_wrapper(*args, **kwargs) -> Any:
                ctx = get_current_context()
                
                if ctx is None:
                    raise RuntimeError(
                        f"LangChain tool '{tool_spec.name}' must be called within a run() block.\n"
                        f"Example:\n"
                        f"  with run(policy='safe') as ctx:\n"
                        f"      safe_tool = guard(langchain_tool, risk='high', effect='fs')\n"
                        f"      safe_tool(...)"
                    )
                
                # Cache key: (tool_id, context_id)
                ctx_id = id(ctx)
                cache_key = (tool_id, ctx_id)
                
                # Register if not already registered (handles context switch)
                if cache_key not in _GUARD_CACHE:
                    if ctx._tools.get(tool_spec.name) is None:
                        ctx._tools.register_tool(tool_spec, auto_assemble=True)
                    _GUARD_CACHE[cache_key] = True
                
                # For LangChain tools, the wrapper function signature doesn't match original
                # Just pass kwargs directly (positional args not supported for LangChain tools)
                if args:
                    raise TypeError(
                        f"LangChain tool '{tool_spec.name}' only supports keyword arguments.\n"
                        f"Use: {tool_spec.name}(arg1=value1, arg2=value2) instead of positional args."
                    )
                
                # Execute through FailCore's Invoker
                return ctx.call(tool_spec.name, **kwargs)
            
            return langchain_wrapper
        
        # Regular Python function - eager registration if in context
        tool_name = func.__name__
        
        # Eager registration: register immediately if in run() context
        if ctx is not None:
            ctx_id = id(ctx)
            cache_key = (tool_id, ctx_id)
            
            if cache_key not in _GUARD_CACHE:
                if ctx._tools.get(tool_name) is None:
                    from ..core.tools.metadata import ToolMetadata
                    
                    metadata = ToolMetadata(
                        risk_level=_map_risk_level(risk),
                        side_effect=_map_side_effect(effect) if effect else None,
                        default_action=_map_default_action(action) if action else _map_default_action("warn"),
                    )
                    
                    ctx.tool(func, metadata=metadata)
                
                _GUARD_CACHE[cache_key] = True
        
        # Regular Python function - use standard flow
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get current run context
            ctx = get_current_context()
            
            if ctx is None:
                raise RuntimeError(
                    f"@guard() decorated function '{func.__name__}' must be called within a run() block.\n"
                    f"Example:\n"
                    f"  with run() as ctx:\n"
                    f"      @guard(risk='high', effect='write')\n"
                    f"      def {func.__name__}(...):\n"
                    f"          ...\n"
                    f"      {func.__name__}(...)"
                )
            
            tool_name = func.__name__
            
            # Cache key: (tool_id, context_id)
            ctx_id = id(ctx)
            cache_key = (tool_id, ctx_id)
            
            # Register if not already registered (handles context switch)
            if cache_key not in _GUARD_CACHE:
                if ctx._tools.get(tool_name) is None:
                    from ..core.tools.metadata import ToolMetadata
                    
                    metadata = ToolMetadata(
                        risk_level=_map_risk_level(risk),
                        side_effect=_map_side_effect(effect) if effect else None,
                        default_action=_map_default_action(action) if action else _map_default_action("warn"),
                    )
                    
                    ctx.tool(func, metadata=metadata)
                
                _GUARD_CACHE[cache_key] = True
            
            # Convert positional args to keyword args
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            params = bound_args.arguments
            
            # Call through context
            return ctx.call(tool_name, **params)
        
        return wrapper
    
    # Support both @guard and @guard() syntax
    if fn is None:
        # @guard() with parentheses
        return decorator
    else:
        # @guard without parentheses
        return decorator(fn)


__all__ = [
    "guard",
]
