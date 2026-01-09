# failcore/core/policy/process_ownership.py
"""
Process Ownership Policy - enforces PID ownership rules

Only allows killing processes that were spawned by the current session.
This prevents unauthorized termination of external processes.
"""

from typing import Optional, Any
from .policy import Policy, PolicyResult
from ..types.step import Step, RunContext


class ProcessOwnershipPolicy(Policy):
    """
    Process ownership policy - only allow killing owned PIDs
    
    This policy enforces that PROCESS_KILL operations can only target
    processes that were spawned by the current session (registered in
    the process registry).
    
    Design:
    - Checks for PROCESS_KILL operations (tool name contains 'kill')
    - Extracts 'pid' parameter from step
    - Checks if PID is in the process registry
    - Denies if PID is not owned by this session
    """
    
    def __init__(self, process_registry: Optional[Any] = None):
        """
        Initialize process ownership policy
        
        Args:
            process_registry: ProcessRegistry instance (optional, for run-scoped checks)
        """
        self.process_registry = process_registry
        self.name = "process_ownership_policy"
    
    def allow(self, step: Step, ctx: RunContext) -> tuple[bool, str] | PolicyResult:
        """
        Check if process operation is allowed
        
        Args:
            step: Step to check
            ctx: Run context
        
        Returns:
            PolicyResult with allow/deny decision
        """
        # Only check PROCESS_KILL operations
        # Heuristic: tool name contains 'kill' or 'terminate'
        tool_name = step.tool.lower() if hasattr(step, 'tool') else ''
        
        is_kill_operation = any(keyword in tool_name for keyword in ['kill', 'terminate', 'stop'])
        
        if not is_kill_operation:
            # Not a kill operation, allow
            return PolicyResult.allow(reason="Not a process kill operation")
        
        # Extract PID from parameters
        params = step.params if hasattr(step, 'params') else {}
        pid = params.get('pid')
        
        if pid is None:
            # No PID parameter, might be a different kind of operation
            return PolicyResult.allow(reason="No PID parameter found")
        
        # Convert to int if string
        try:
            pid = int(pid)
        except (ValueError, TypeError):
            return PolicyResult.deny(
                reason=f"Invalid PID parameter: {pid}",
                error_code="INVALID_PID",
                details={"pid": str(pid), "tool": step.tool},
            )
        
        # Check if process registry is available
        if not self.process_registry:
            # No registry configured - allow (backward compatibility)
            return PolicyResult.allow(reason="Process registry not configured")
        
        # Check if PID is owned by this session
        if not self.process_registry.is_owned(pid):
            # PID not owned - deny
            return PolicyResult.deny(
                reason=f"Cannot kill process {pid}: PID not owned by this session (spawn registry mismatch)",
                error_code="PID_NOT_OWNED",
                details={
                    "pid": pid,
                    "tool": step.tool,
                    "owned_pids": list(self.process_registry.get_owned_pids()),
                },
                suggestion="Only processes spawned by this session can be killed",
            )
        
        # PID is owned - allow
        return PolicyResult.allow(
            reason=f"Process {pid} is owned by this session"
        )


__all__ = ["ProcessOwnershipPolicy"]
