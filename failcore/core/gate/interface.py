"""
Gate Interface - Abstract gate contract

Defines what a gate must implement regardless of boundary type.
"""

from __future__ import annotations

from typing import Optional, Any, Dict, Protocol
from dataclasses import dataclass

from ..guards.semantic.verdict import VerdictAction
from ..events.attempt import AttemptEvent


@dataclass
class GateContext:
    """
    Context passed to gate for decision making
    
    Contains all information needed for gate to make verdict.
    Same structure for both preflight and egress gates.
    """
    # Identity
    run_id: str
    step_id: Optional[str] = None
    attempt_id: Optional[str] = None
    
    # Tool context
    tool: str = ""
    params: Optional[Dict[str, Any]] = None
    
    # Request context (for egress gate)
    method: Optional[str] = None
    endpoint: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    body: Optional[bytes] = None
    
    # Additional context
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class GateVerdict:
    """
    Gate verdict result
    
    Returned by gate.check() to indicate decision.
    Will be written into AttemptEvent.
    """
    action: VerdictAction
    reason: str
    rule_name: Optional[str] = None
    rule_category: Optional[str] = None
    confidence: float = 1.0
    
    # Modified params (if SANITIZE action)
    sanitized_params: Optional[Dict[str, Any]] = None
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None


class Gate(Protocol):
    """
    Abstract Gate protocol
    
    All gates (preflight or egress) must implement this interface.
    
    Architecture constraint:
    - Gate is the ONLY entity allowed to write VERDICT
    - Gate must produce AttemptEvent regardless of verdict (for audit trail)
    - Gate verdict is final and authoritative
    
    Usage:
    ```python
    gate = PreflightGate(rules=...)
    context = GateContext(tool="write_file", params={...})
    verdict = gate.check(context)
    
    if verdict.action == VerdictAction.BLOCK:
        # Execution prevented
        # But AttemptEvent still written to trace
        pass
    ```
    """
    
    def check(self, context: GateContext) -> GateVerdict:
        """
        Check context and return verdict
        
        Args:
            context: Gate context with tool/params/request info
        
        Returns:
            GateVerdict with action and reason
        
        Raises:
            Never raises - always returns verdict (fail-open on error)
        """
        ...
    
    def create_attempt_event(
        self,
        context: GateContext,
        verdict: GateVerdict,
    ) -> AttemptEvent:
        """
        Create attempt event from context and verdict
        
        Args:
            context: Gate context
            verdict: Gate verdict
        
        Returns:
            AttemptEvent ready to write to trace
        
        Note:
            This event written BEFORE execution (regardless of verdict)
        """
        ...


__all__ = ["Gate", "GateContext", "GateVerdict"]
