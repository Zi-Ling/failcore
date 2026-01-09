# failcore/utils/process.py
"""
Robust cross-platform process management utilities.

Provides platform-agnostic APIs for process control with proper error handling,
timeouts, and fallback strategies.
"""

import os
import signal
import subprocess
import sys
import time
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ProcessError(Exception):
    """Base exception for process management errors"""
    pass


class ProcessKillError(ProcessError):
    """Raised when process termination fails"""
    pass


class ProcessCheckError(ProcessError):
    """Raised when process existence check fails"""
    pass


def pid_exists(pid: int, timeout: float = 2.0) -> bool:
    """
    Check if a process exists by PID.
    
    Cross-platform implementation with timeout and error handling.
    
    Args:
        pid: Process ID to check
        timeout: Timeout in seconds for the check operation
        
    Returns:
        True if process exists, False otherwise
        
    Note:
        - Windows: uses tasklist (reliable but slower)
        - Unix: uses os.kill(pid, 0) (fast)
    """
    try:
        if sys.platform == 'win32':
            # Windows: use tasklist to check if PID exists
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            # tasklist outputs the PID in the result if it exists
            return str(pid) in result.stdout
        else:
            # Unix: use os.kill with signal 0 (doesn't send signal, just checks)
            try:
                os.kill(pid, 0)
                return True
            except (ProcessLookupError, PermissionError):
                return False
    except subprocess.TimeoutExpired:
        logger.warning(f"PID check timed out for {pid} after {timeout}s")
        return False
    except Exception as e:
        logger.warning(f"PID check failed for {pid}: {e}")
        # Conservative: assume process exists to avoid false negatives
        return True


def kill_process(
    pid: int,
    force: bool = True,
    timeout: float = 5.0,
    verify: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Kill a process by PID with timeout and fallback strategies.
    
    Strategy:
    1. Try graceful termination (SIGTERM on Unix, taskkill on Windows)
    2. If process still alive after timeout/2, force kill (SIGKILL/taskkill /F)
    3. Verify termination if requested
    
    Args:
        pid: Process ID to kill
        force: If True, use SIGKILL/taskkill /F immediately
        timeout: Total timeout for kill operation
        verify: If True, verify process is actually dead
        
    Returns:
        Tuple of (success, error_message)
        - (True, None) if process killed successfully
        - (False, error_msg) if kill failed
        
    Raises:
        ProcessKillError: If kill fails and verify=True
    """
    start_time = time.time()
    error_msg = None
    
    try:
        # Check if process exists first
        if not pid_exists(pid, timeout=min(1.0, timeout / 4)):
            logger.debug(f"Process {pid} does not exist, skip kill")
            return (True, None)
        
        if sys.platform == 'win32':
            # Windows: use taskkill
            if force:
                # Force kill immediately
                result = subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=timeout / 2
                )
                success = result.returncode == 0
            else:
                # Try graceful first, then force
                result = subprocess.run(
                    ['taskkill', '/PID', str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=timeout / 3
                )
                
                if result.returncode == 0:
                    # Wait for graceful termination
                    time.sleep(0.5)
                    if pid_exists(pid, timeout=0.5):
                        # Still alive, force kill
                        result = subprocess.run(
                            ['taskkill', '/F', '/PID', str(pid)],
                            capture_output=True,
                            text=True,
                            timeout=timeout / 3
                        )
                success = result.returncode == 0
                
            if not success:
                error_msg = f"taskkill failed: {result.stderr}"
        else:
            # Unix: use signals
            try:
                if force:
                    os.kill(pid, signal.SIGKILL)
                else:
                    # Try SIGTERM first
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)
                    
                    # Check if still alive
                    if pid_exists(pid, timeout=0.5):
                        # Force kill
                        os.kill(pid, signal.SIGKILL)
                
                success = True
            except ProcessLookupError:
                # Process already dead
                success = True
            except PermissionError as e:
                success = False
                error_msg = f"Permission denied: {e}"
            except OSError as e:
                success = False
                error_msg = f"OS error: {e}"
        
        # Verify termination
        if verify and success:
            # Wait a bit for process to actually terminate
            elapsed = time.time() - start_time
            remaining = max(0.1, timeout - elapsed)
            
            max_wait = min(remaining, 2.0)
            wait_interval = 0.1
            waited = 0.0
            
            while waited < max_wait:
                if not pid_exists(pid, timeout=0.5):
                    logger.debug(f"Process {pid} terminated successfully")
                    return (True, None)
                time.sleep(wait_interval)
                waited += wait_interval
            
            # Still alive after verification
            error_msg = f"Process {pid} still alive after kill"
            success = False
        
        if not success and error_msg:
            logger.error(f"Failed to kill process {pid}: {error_msg}")
            if verify:
                raise ProcessKillError(error_msg)
        
        return (success, error_msg)
        
    except subprocess.TimeoutExpired as e:
        error_msg = f"Kill operation timed out after {timeout}s"
        logger.error(f"Failed to kill process {pid}: {error_msg}")
        if verify:
            raise ProcessKillError(error_msg)
        return (False, error_msg)
    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {e}"
        logger.error(f"Failed to kill process {pid}: {error_msg}")
        if verify:
            raise ProcessKillError(error_msg)
        return (False, error_msg)


def cleanup_processes(pids: list[int], timeout: float = 10.0) -> dict[int, bool]:
    """
    Cleanup multiple processes with best-effort strategy.
    
    Args:
        pids: List of PIDs to cleanup
        timeout: Total timeout for all cleanup operations
        
    Returns:
        Dict mapping PID to cleanup success status
    """
    results = {}
    timeout_per_pid = timeout / max(len(pids), 1)
    
    for pid in pids:
        success, error = kill_process(
            pid,
            force=True,
            timeout=timeout_per_pid,
            verify=False  # Best-effort, don't raise
        )
        results[pid] = success
        if not success:
            logger.warning(f"Failed to cleanup process {pid}: {error}")
    
    return results


def create_process_group() -> Optional[int]:
    """
    Create a new process group for the current process.
    
    Platform-specific implementation:
    - Unix: Use os.setsid() to create new session and process group
    - Windows: Return flag for CREATE_NEW_PROCESS_GROUP (caller must use in subprocess)
    
    Returns:
        - Unix: Process group ID (same as PID after setsid)
        - Windows: None (flag must be passed to subprocess.Popen creationflags)
        
    Note:
        On Unix, this must be called BEFORE forking child processes.
        On Windows, this returns None; use get_process_group_creation_flags() instead.
    """
    if sys.platform == 'win32':
        # Windows: Cannot set process group for current process
        # Return None - caller must use creationflags in subprocess.Popen
        logger.warning("create_process_group() on Windows returns None - use get_process_group_creation_flags() for subprocess")
        return None
    else:
        # Unix: Create new session (becomes process group leader)
        try:
            pgid = os.setsid()
            logger.debug(f"Created new process group: {pgid}")
            return pgid
        except OSError as e:
            logger.error(f"Failed to create process group: {e}")
            raise ProcessError(f"Failed to create process group: {e}")


def get_process_group_creation_flags() -> int:
    """
    Get platform-specific flags for creating a process in a new process group.
    
    Returns:
        - Windows: CREATE_NEW_PROCESS_GROUP flag (0x00000200)
        - Unix: 0 (process group creation handled by os.setsid)
        
    Usage:
        subprocess.Popen(
            cmd,
            creationflags=get_process_group_creation_flags()
        )
    """
    if sys.platform == 'win32':
        # Windows: CREATE_NEW_PROCESS_GROUP
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        return CREATE_NEW_PROCESS_GROUP
    else:
        # Unix: Use preexec_fn=os.setsid instead
        return 0


def kill_process_group(
    pgid: int,
    timeout: float = 5.0,
    signal_escalation: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Kill an entire process group.
    
    Strategy:
    - Unix: Use os.killpg() to send signal to entire process group
    - Windows: v1 uses taskkill /T (tree kill), v2 would use Job Objects
    
    Args:
        pgid: Process group ID (Unix) or root PID (Windows)
        timeout: Timeout for kill operation
        signal_escalation: If True, try SIGTERM then SIGKILL (Unix only)
        
    Returns:
        Tuple of (success, error_message)
        
    Note:
        - Unix: PGID must be a valid process group leader
        - Windows: Falls back to tree kill (less reliable, v2 needs Job Objects)
    """
    start_time = time.time()
    
    try:
        if sys.platform == 'win32':
            # Windows v1: Use taskkill /T (tree kill)
            # Note: This is best-effort; full solution needs Job Objects (v2)
            logger.info(f"Killing process tree rooted at PID {pgid} (Windows)")
            
            try:
                result = subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pgid)],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode == 0:
                    logger.info(f"Successfully killed process tree {pgid}")
                    return (True, None)
                else:
                    error_msg = f"taskkill /T failed: {result.stderr}"
                    logger.error(error_msg)
                    return (False, error_msg)
                    
            except subprocess.TimeoutExpired:
                error_msg = f"Process tree kill timed out after {timeout}s"
                logger.error(error_msg)
                return (False, error_msg)
        else:
            # Unix: Use os.killpg() for proper process group kill
            logger.info(f"Killing process group {pgid} (Unix)")
            
            try:
                if signal_escalation:
                    # Try SIGTERM first
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                        logger.debug(f"Sent SIGTERM to process group {pgid}")
                        
                        # Wait briefly for graceful termination
                        time.sleep(0.5)
                        
                        # Check if group leader still exists
                        if pid_exists(pgid, timeout=0.5):
                            # Still alive, escalate to SIGKILL
                            os.killpg(pgid, signal.SIGKILL)
                            logger.debug(f"Sent SIGKILL to process group {pgid}")
                    except ProcessLookupError:
                        # Process group already dead after SIGTERM
                        pass
                else:
                    # Direct SIGKILL
                    os.killpg(pgid, signal.SIGKILL)
                
                # Verify termination
                elapsed = time.time() - start_time
                remaining = max(0.1, timeout - elapsed)
                
                max_wait = min(remaining, 2.0)
                wait_interval = 0.1
                waited = 0.0
                
                while waited < max_wait:
                    if not pid_exists(pgid, timeout=0.5):
                        logger.info(f"Process group {pgid} terminated successfully")
                        return (True, None)
                    time.sleep(wait_interval)
                    waited += wait_interval
                
                # Still alive after wait
                error_msg = f"Process group {pgid} still alive after kill"
                logger.error(error_msg)
                return (False, error_msg)
                
            except ProcessLookupError:
                # Process group already dead
                logger.debug(f"Process group {pgid} already terminated")
                return (True, None)
            except PermissionError as e:
                error_msg = f"Permission denied killing process group {pgid}: {e}"
                logger.error(error_msg)
                return (False, error_msg)
            except OSError as e:
                error_msg = f"OS error killing process group {pgid}: {e}"
                logger.error(error_msg)
                return (False, error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error killing process group {pgid}: {e}"
        logger.error(error_msg)
        return (False, error_msg)


__all__ = [
    "ProcessError",
    "ProcessKillError",
    "ProcessCheckError",
    "pid_exists",
    "kill_process",
    "cleanup_processes",
    "create_process_group",
    "get_process_group_creation_flags",
    "kill_process_group",
]
