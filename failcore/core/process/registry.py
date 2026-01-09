# failcore/core/process/registry.py
"""
Process Registry - tracks owned PIDs for a run session

This registry is run-scoped and tracks which processes were spawned
by the current session. It's used to enforce process ownership policies:
only allow killing processes that were spawned by the current session.

Provides robust cleanup using failcore.utils.process for proper resource management.
"""

from typing import Set, Optional, Dict
import threading
import logging

# Import robust process management utilities
from failcore.utils.process import kill_process, cleanup_processes, pid_exists

logger = logging.getLogger(__name__)


class ProcessRegistry:
    """
    Run-scoped process registry that tracks owned PIDs
    
    Thread-safe registry for tracking which processes belong to the current run.
    Used to enforce process ownership policies (only kill owned processes).
    
    Features:
    - Automatic cleanup of owned processes on context exit
    - Robust cross-platform process termination
    - Timeout and error handling for all operations
    """
    
    def __init__(self, auto_cleanup: bool = True, pgid: Optional[int] = None):
        """
        Initialize process registry
        
        Args:
            auto_cleanup: If True, automatically cleanup owned processes on __del__
            pgid: Process group ID (if managing a process group)
        """
        self._owned_pids: Set[int] = set()
        self._pgid = pgid  # Process group ID for group-level kill
        self._lock = threading.Lock()
        self._auto_cleanup = auto_cleanup
        self._cleaned_up = False
    
    def register_pid(self, pid: int) -> None:
        """
        Register a PID as owned by this session
        
        Args:
            pid: Process ID to register
        """
        with self._lock:
            self._owned_pids.add(pid)
            logger.debug(f"Registered PID {pid} as owned by this session")
    
    def unregister_pid(self, pid: int) -> None:
        """
        Remove a PID from the owned set (optional cleanup)
        
        Args:
            pid: Process ID to unregister
        """
        with self._lock:
            self._owned_pids.discard(pid)
            logger.debug(f"Unregistered PID {pid} from this session")
    
    def is_owned(self, pid: int) -> bool:
        """
        Check if a PID is owned by this session
        
        Args:
            pid: Process ID to check
        
        Returns:
            True if PID is owned by this session, False otherwise
        """
        with self._lock:
            return pid in self._owned_pids
    
    def get_owned_pids(self) -> Set[int]:
        """
        Get a copy of all owned PIDs
        
        Returns:
            Set of owned PIDs
        """
        with self._lock:
            return self._owned_pids.copy()
    
    def set_process_group(self, pgid: int) -> None:
        """
        Set process group ID for group-level cleanup
        
        Args:
            pgid: Process group ID
        """
        with self._lock:
            self._pgid = pgid
            logger.debug(f"Set process group ID: {pgid}")
    
    def get_process_group(self) -> Optional[int]:
        """Get process group ID"""
        with self._lock:
            return self._pgid
    
    def cleanup(self, timeout: float = 10.0, force: bool = True, use_process_group: bool = True) -> Dict[int, bool]:
        """
        Cleanup all owned processes with robust error handling
        
        Strategy:
        1. If process group is set and use_process_group=True, kill entire group (more reliable)
        2. Otherwise, fall back to individual PID cleanup
        
        Args:
            timeout: Total timeout for cleanup operations
            force: If True, use force kill (SIGKILL/taskkill /F)
            use_process_group: If True and pgid is set, use process group kill
            
        Returns:
            Dict mapping PID to cleanup success status
            
        Note:
            - Prefers process group kill (more reliable, catches grandchildren)
            - Falls back to individual PID cleanup if no process group
            - Uses robust kill_process/kill_process_group from failcore.utils.process
            - Handles all exceptions gracefully
            - Best-effort: continues even if some PIDs fail
        """
        with self._lock:
            if self._cleaned_up:
                logger.debug("Process registry already cleaned up")
                return {}
            
            pids = list(self._owned_pids)
            pgid = self._pgid
            self._cleaned_up = True
        
        if not pids and not pgid:
            logger.debug("No processes to cleanup")
            return {}
        
        # Strategy 1: Process group kill (preferred, more reliable)
        if use_process_group and pgid:
            logger.info(f"Cleaning up process group {pgid} (contains {len(pids)} registered PIDs)")
            
            try:
                from failcore.utils.process import kill_process_group
                
                success, error = kill_process_group(
                    pgid,
                    timeout=timeout,
                    signal_escalation=not force
                )
                
                if success:
                    logger.info(f"Successfully cleaned up process group {pgid}")
                    # Return success for all registered PIDs
                    return {pid: True for pid in pids}
                else:
                    logger.error(f"Failed to cleanup process group {pgid}: {error}")
                    # Fall through to individual cleanup
            except Exception as e:
                logger.error(f"Error during process group cleanup: {e}", exc_info=True)
                # Fall through to individual cleanup
        
        # Strategy 2: Individual PID cleanup (fallback)
        if pids:
            logger.info(f"Cleaning up {len(pids)} individual processes: {pids}")
            
            try:
                # Use robust cleanup_processes from utils
                results = cleanup_processes(pids, timeout=timeout)
                
                # Log results
                success_count = sum(1 for v in results.values() if v)
                fail_count = len(results) - success_count
                
                if fail_count > 0:
                    failed_pids = [pid for pid, success in results.items() if not success]
                    logger.warning(f"Failed to cleanup {fail_count} processes: {failed_pids}")
                else:
                    logger.info(f"Successfully cleaned up all {success_count} processes")
                
                return results
                
            except Exception as e:
                logger.error(f"Unexpected error during process cleanup: {e}", exc_info=True)
                # Return failure for all PIDs
                return {pid: False for pid in pids}
        
        return {}
    
    def clear(self) -> None:
        """Clear all registered PIDs without cleanup"""
        with self._lock:
            self._owned_pids.clear()
            logger.debug("Cleared process registry")
    
    def __del__(self):
        """Cleanup owned processes on deletion (if auto_cleanup enabled)"""
        if self._auto_cleanup and not self._cleaned_up:
            try:
                self.cleanup(timeout=5.0, force=True)
            except Exception as e:
                # Don't raise in __del__
                logger.error(f"Error in ProcessRegistry.__del__: {e}")
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on context exit"""
        try:
            self.cleanup(timeout=10.0, force=True)
        except Exception as e:
            logger.error(f"Error during ProcessRegistry cleanup: {e}")
        return False  # Don't suppress exceptions


__all__ = ["ProcessRegistry"]
