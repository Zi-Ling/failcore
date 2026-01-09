"""
Attempt Event - Pre-execution event model

Written by gates BEFORE execution to capture:
- What was attempted
- Gate verdict (ALLOW/BLOCK/SANITIZE)
- Pre-execution context

Design:
- Single event per attempt (not START/END split)
- Includes verdict inline (no separate verdict event)
- Stable attempt_id for correlation

This solves "guard阻断无法留证据" problem by ensuring
all attempts are recorded regardless of verdict.
"""

from __future__ import annotations

from typing import Optional, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..rules.schemas import VerdictSchema, TargetSchema


class AttemptStatus(str, Enum):
    """Attempt status"""
    PENDING = "pending"        # Attempt registered, not yet executed
    ALLOWED = "allowed"        # Gate allowed, execution proceeding
    BLOCKED = "blocked"        # Gate blocked, execution prevented
    SANITIZED = "sanitized"    # Gate sanitized parameters
    WARNED = "warned"          # Gate issued warning but allowed
    ERROR = "error"            # Gate evaluation error


@dataclass
class AttemptEvent:
    """
    Attempt event - pre-execution record
    
    Written by gates (preflight or egress) BEFORE execution.
    Captures intent, parameters, and gate verdict.
    
    Architecture constraint:
    - attempt_id MUST be stable and unique
    - verdict MUST be included (not separate event)
    - This event written regardless of verdict (ALLOW/BLOCK/etc)
    
    Field structure same as EgressEvent to ensure homogeneous trace.
    """
    # Identity
    attempt_id: str
    run_id: str
    step_id: Optional[str] = None
    
    # Timing
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Tool context
    tool: str = ""
    params: Optional[Dict[str, Any]] = None
    
    # Gate verdict (REQUIRED - this is the key difference from old model)
    verdict: Optional[VerdictSchema] = None
    status: AttemptStatus = AttemptStatus.PENDING
    
    # Target (inferred from params)
    target: Optional[TargetSchema] = None
    
    # Metadata
    gate_type: str = "preflight"  # "preflight" or "egress"
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        data = {
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "ts": self.ts,
            "tool": self.tool,
            "params": self.params,
            "status": self.status.value if isinstance(self.status, AttemptStatus) else self.status,
            "gate_type": self.gate_type,
        }
        
        if self.verdict:
            data["verdict"] = {
                "action": self.verdict.action.value if hasattr(self.verdict.action, 'value') else self.verdict.action,
                "reason": self.verdict.reason,
                "rule_name": self.verdict.rule_name,
                "confidence": self.verdict.confidence,
            }
        
        if self.target:
            data["target"] = {
                "type": self.target.type.value if hasattr(self.target.type, 'value') else self.target.type,
                "inferred": self.target.inferred,
                "inferred_confidence": self.target.inferred_confidence,
            }
        
        if self.context:
            data["context"] = self.context
        
        return data


__all__ = ["AttemptEvent", "AttemptStatus"]
