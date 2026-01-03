# failcore/api/guard.py
"""
Guard decorator - automatically inherits run context configuration
"""

from __future__ import annotations
from functools import wraps
from typing import Any, Callable, Optional, Literal
import inspect

from ..core.step import StepStatus
from .context import get_current_context


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
    
    Args:
        fn: Function to decorate (optional, supports @guard and @guard())
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
    
    With Description:
        >>> with run() as ctx:
        ...     @guard(risk="high", effect="write", description="Write to file")
        ...     def write_file(path: str, content: str):
        ...         with open(path, "w") as f:
        ...             f.write(content)
        ...     
        ...     write_file(path="data.txt", content="hello")
    
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
    """
    
    def decorator(func: Callable) -> Callable:
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
            
            # Auto-register tool with metadata if not already registered
            if ctx._tools.get(tool_name) is None:
                # Build metadata from simple parameters
                from ..core.tools.metadata import ToolMetadata
                
                metadata = ToolMetadata(
                    risk_level=_map_risk_level(risk),
                    side_effect=_map_side_effect(effect) if effect else None,
                    default_action=_map_default_action(action) if action else _map_default_action("warn"),
                )
                
                # Register with metadata
                ctx.tool(func, metadata=metadata)
            
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
