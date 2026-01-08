# failcore/hooks/subprocess_patch.py
"""
Subprocess monkey-patch - Emit EgressEvent for all subprocess calls

Patches subprocess.run, subprocess.Popen to intercept executions.
"""

from typing import Optional
import time

from failcore.core.egress import EgressEngine, EgressEvent, EgressType, PolicyDecision, RiskLevel


_original_subprocess_run = None
_original_subprocess_popen = None
_egress_engine: Optional[EgressEngine] = None


def patch_subprocess(egress_engine: EgressEngine) -> None:
    """
    Patch subprocess to emit egress events
    
    Args:
        egress_engine: EgressEngine for event routing
    """
    global _egress_engine, _original_subprocess_run, _original_subprocess_popen
    
    import subprocess
    
    _egress_engine = egress_engine
    
    # Patch subprocess.run
    _original_subprocess_run = subprocess.run
    subprocess.run = _patched_subprocess_run
    
    # Patch subprocess.Popen
    _original_subprocess_popen = subprocess.Popen
    subprocess.Popen = _patched_subprocess_popen


def unpatch_subprocess() -> None:
    """Restore original subprocess methods"""
    global _egress_engine, _original_subprocess_run, _original_subprocess_popen
    
    import subprocess
    
    if _original_subprocess_run:
        subprocess.run = _original_subprocess_run
        _original_subprocess_run = None
    
    if _original_subprocess_popen:
        subprocess.Popen = _original_subprocess_popen
        _original_subprocess_popen = None
    
    _egress_engine = None


def _patched_subprocess_run(*args, **kwargs):
    """Patched subprocess.run"""
    start_time = time.time()
    run_id = "subprocess_hook"
    step_id = f"exec_{int(start_time * 1000)}"
    
    # Extract command
    cmd = args[0] if args else kwargs.get("args", "unknown")
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    
    # Emit pre-call event
    if _egress_engine:
        _emit_exec_event(cmd_str, run_id, step_id, "pre_call")
    
    # Call original
    try:
        result = _original_subprocess_run(*args, **kwargs)
        
        # Emit post-call event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_exec_event(cmd_str, run_id, step_id, "post_call",
                           response={"returncode": result.returncode}, duration_ms=duration_ms)
        
        return result
    except Exception as e:
        # Emit error event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_exec_event(cmd_str, run_id, step_id, "post_call",
                           error={"type": type(e).__name__, "message": str(e)}, duration_ms=duration_ms)
        raise


def _patched_subprocess_popen(*args, **kwargs):
    """Patched subprocess.Popen"""
    start_time = time.time()
    run_id = "subprocess_hook"
    step_id = f"exec_{int(start_time * 1000)}"
    
    # Extract command
    cmd = args[0] if args else kwargs.get("args", "unknown")
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    
    # Emit event
    if _egress_engine:
        _emit_exec_event(cmd_str, run_id, step_id, "popen")
    
    # Call original
    return _original_subprocess_popen(*args, **kwargs)


def _emit_exec_event(
    command: str,
    run_id: str,
    step_id: str,
    phase: str,
    response: Optional[dict] = None,
    error: Optional[dict] = None,
    duration_ms: float = 0,
) -> None:
    """Emit EXEC egress event"""
    if not _egress_engine:
        return
    
    event = EgressEvent(
        egress=EgressType.EXEC,
        action="subprocess.exec",
        target=command,
        run_id=run_id,
        step_id=step_id,
        tool_name="subprocess_hook",
        decision=PolicyDecision.ALLOW if not error else PolicyDecision.DENY,
        risk=RiskLevel.MEDIUM,  # EXEC is inherently higher risk
        evidence={
            "command": command,
            "phase": phase,
            "response": response,
            "error": error,
            "duration_ms": duration_ms,
        },
    )
    
    try:
        _egress_engine.emit(event)
    except Exception:
        # Hook emission must not break user code
        pass


__all__ = ["patch_subprocess", "unpatch_subprocess"]
