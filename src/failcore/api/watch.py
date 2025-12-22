# failcore/api/watch.py
"""
Watch decorator - magical wrapper for automatic trace and validation

Usage:
    from failcore import watch, Session
    
    @watch
    def read_file(path: str) -> str:
        with open(path) as f:
            return f.read()
    
    session = Session()
    result = read_file(path="data.txt")  # Automatically traced and validated
"""

from __future__ import annotations
from functools import wraps
from typing import Any, Callable, Optional
import inspect
from ..core.step import Step, StepResult, StepStatus, StepOutput, OutputKind, generate_step_id
from ..core.executor.executor import Executor


# Global session registry for @watch decorator
_WATCH_SESSION: Optional[Any] = None


def set_watch_session(session: Any):
    """
    Set the global session for @watch decorator
    
    Args:
        session: Session instance to use for @watch decorated functions
    """
    global _WATCH_SESSION
    _WATCH_SESSION = session


def get_watch_session() -> Optional[Any]:
    """Get the current watch session"""
    return _WATCH_SESSION


def watch(fn: Callable) -> Callable:
    """
    Decorator to automatically trace and validate function calls
    
    Features:
    - Automatic trace recording (if session has trace enabled)
    - Automatic validation (if session has validator configured)
    - Automatic policy enforcement (if session has policy configured)
    - Exception handling and error recording
    
    Usage:
        # Method 1: Use with global session
        from failcore import watch, Session
        
        session = Session()  # Automatically becomes the watch session
        
        @watch
        def read_file(path: str) -> str:
            with open(path) as f:
                return f.read()
        
        result = read_file(path="data.txt")
        
        # Method 2: Explicit session binding
        from failcore import watch, set_watch_session
        
        set_watch_session(my_session)
        
        @watch
        def my_tool(x: int) -> int:
            return x * 2
    
    Args:
        fn: Function to wrap
    
    Returns:
        Wrapped function that returns StepResult
    """
    
    @wraps(fn)
    def wrapper(**kwargs) -> StepResult:
        # Get the current watch session
        session = get_watch_session()
        
        if session is None:
            # No session - execute directly without tracing
            try:
                result = fn(**kwargs)
                return StepResult(
                    step_id=generate_step_id(),
                    status=StepStatus.OK,
                    output=StepOutput(kind=OutputKind.VALUE, value=result),
                    phase="executed"
                )
            except Exception as e:
                return StepResult(
                    step_id=generate_step_id(),
                    status=StepStatus.FAIL,
                    error={"code": "EXECUTION_ERROR", "message": str(e)},
                    phase="failed"
                )
        
        # Use session to execute the tool
        tool_name = fn.__name__
        
        # Register the tool if not already registered
        if session._tools.get(tool_name) is None:
            session.register(tool_name, fn)
        
        # Execute through session
        return session.call(tool_name, **kwargs)
    
    return wrapper


class WatchContext:
    """
    Context manager for scoped watch sessions
    
    Usage:
        with WatchContext(session):
            @watch
            def my_tool():
                pass
            
            my_tool()  # Uses the context session
    """
    
    def __init__(self, session: Any):
        self.session = session
        self.previous_session = None
    
    def __enter__(self):
        self.previous_session = get_watch_session()
        set_watch_session(self.session)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        set_watch_session(self.previous_session)


__all__ = [
    "watch",
    "set_watch_session",
    "get_watch_session",
    "WatchContext",
]
