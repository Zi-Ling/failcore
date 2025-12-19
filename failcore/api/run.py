# failcore/api/run.py
"""
Run API - one-line execution for quick testing and single-step operations
"""

from typing import Any, Dict, Optional
from ..core.step import Step, RunContext, StepResult, new_step_id, new_run_id
from ..core.executor.executor import Executor, ExecutorConfig
from ..core.tools.registry import ToolRegistry
from ..core.trace.recorder import JsonlTraceRecorder, NullTraceRecorder


def run(
    tool: str,
    trace: Optional[str] = None,
    _tools: Optional[ToolRegistry] = None,
    **params: Any
) -> StepResult:
    """
    Run API - execute a single tool call in one line
    
    User only needs to provide: tool name + parameters + optional trace path
    
    Args:
        tool: Tool name
        trace: Optional trace file path (.jsonl), None for no recording
        _tools: Internal parameter - tool registry (usually not needed)
        **params: Tool parameters
    
    Returns:
        StepResult: Execution result (ok/fail + output/error)
    
    Examples:
        >>> from failcore import Session, run
        >>> # Method 1: Register tools via Session (advanced)
        >>> # Method 2: Quick test with _tools parameter
        >>> from failcore import ToolRegistry
        >>> tools = ToolRegistry()
        >>> tools.register("divide", lambda a, b: a / b)
        >>> result = run("divide", _tools=tools, a=6, b=2, trace="trace.jsonl")
        >>> print(result.output.value)
    
    Note:
        - Run API is mainly for testing, scripts, and similar scenarios
        - For production, use Session API instead
        - No need for session, ctx, or step_id management
        - Automatically generates run_id and step_id
        - Automatically creates recorder (trace=None means no-op)
        - Automatically closes after execution
    """
    # Auto-generate IDs
    run_id = new_run_id()
    step_id = new_step_id()
    
    # Use provided tool registry or create empty one
    tools = _tools or ToolRegistry()
    
    # Create recorder
    recorder = JsonlTraceRecorder(trace) if trace else NullTraceRecorder()
    
    # Create executor
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig()
    )
    
    # Create step
    step = Step(
        id=step_id,
        tool=tool,
        params=params
    )
    
    # Create context
    ctx = RunContext(run_id=run_id)
    
    # Execute
    result = executor.execute(step, ctx)
    
    # Close recorder
    if hasattr(recorder, 'close'):
        try:
            recorder.close()
        except Exception:
            pass
    
    return result
