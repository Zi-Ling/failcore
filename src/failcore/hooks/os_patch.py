# failcore/hooks/os_patch.py
"""
OS/filesystem monkey-patch - Emit EgressEvent for file operations

Patches os.open, os.remove, os.rename, etc. to intercept FS operations.
"""

from typing import Optional
import os

from failcore.core.egress import EgressEngine, EgressEvent, EgressType, PolicyDecision, RiskLevel


_original_os_open = None
_original_os_remove = None
_original_os_rename = None
_original_os_mkdir = None
_original_os_rmdir = None
_egress_engine: Optional[EgressEngine] = None


def patch_os(egress_engine: EgressEngine) -> None:
    """
    Patch os module to emit egress events
    
    Args:
        egress_engine: EgressEngine for event routing
    """
    global _egress_engine
    global _original_os_open, _original_os_remove, _original_os_rename
    global _original_os_mkdir, _original_os_rmdir
    
    _egress_engine = egress_engine
    
    # Patch file operations
    _original_os_open = os.open
    os.open = _patched_os_open
    
    _original_os_remove = os.remove
    os.remove = _patched_os_remove
    
    _original_os_rename = os.rename
    os.rename = _patched_os_rename
    
    _original_os_mkdir = os.mkdir
    os.mkdir = _patched_os_mkdir
    
    _original_os_rmdir = os.rmdir
    os.rmdir = _patched_os_rmdir


def unpatch_os() -> None:
    """Restore original os methods"""
    global _egress_engine
    global _original_os_open, _original_os_remove, _original_os_rename
    global _original_os_mkdir, _original_os_rmdir
    
    if _original_os_open:
        os.open = _original_os_open
        _original_os_open = None
    
    if _original_os_remove:
        os.remove = _original_os_remove
        _original_os_remove = None
    
    if _original_os_rename:
        os.rename = _original_os_rename
        _original_os_rename = None
    
    if _original_os_mkdir:
        os.mkdir = _original_os_mkdir
        _original_os_mkdir = None
    
    if _original_os_rmdir:
        os.rmdir = _original_os_rmdir
        _original_os_rmdir = None
    
    _egress_engine = None


def _patched_os_open(path, flags, *args, **kwargs):
    """Patched os.open"""
    # Emit event
    if _egress_engine:
        _emit_fs_event("os.open", str(path), "open")
    
    return _original_os_open(path, flags, *args, **kwargs)


def _patched_os_remove(path):
    """Patched os.remove"""
    # Emit event
    if _egress_engine:
        _emit_fs_event("os.remove", str(path), "delete")
    
    return _original_os_remove(path)


def _patched_os_rename(src, dst):
    """Patched os.rename"""
    # Emit event
    if _egress_engine:
        _emit_fs_event("os.rename", f"{src} -> {dst}", "rename")
    
    return _original_os_rename(src, dst)


def _patched_os_mkdir(path, *args, **kwargs):
    """Patched os.mkdir"""
    # Emit event
    if _egress_engine:
        _emit_fs_event("os.mkdir", str(path), "mkdir")
    
    return _original_os_mkdir(path, *args, **kwargs)


def _patched_os_rmdir(path):
    """Patched os.rmdir"""
    # Emit event
    if _egress_engine:
        _emit_fs_event("os.rmdir", str(path), "rmdir")
    
    return _original_os_rmdir(path)


def _emit_fs_event(action: str, target: str, operation: str) -> None:
    """Emit FS egress event"""
    if not _egress_engine:
        return
    
    import time
    run_id = "os_hook"
    step_id = f"fs_{int(time.time() * 1000)}"
    
    event = EgressEvent(
        egress=EgressType.FS,
        action=action,
        target=target,
        run_id=run_id,
        step_id=step_id,
        tool_name="os_hook",
        decision=PolicyDecision.ALLOW,
        risk=RiskLevel.MEDIUM,  # FS operations are medium risk
        evidence={
            "operation": operation,
            "path": target,
        },
    )
    
    try:
        _egress_engine.emit(event)
    except Exception:
        # Hook emission must not break user code
        pass


__all__ = ["patch_os", "unpatch_os"]
