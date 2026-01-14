# failcore/core/validate/audit.py
"""

Policy Audit - Breakglass and override audit trail

Tracks who enabled breakglass, when, why, and which decisions were affected.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field

from .contracts import Policy, Decision


@dataclass
class BreakglassAuditRecord:
    """
    Audit record for breakglass activation
    
    Records:
    - Who enabled it (user/environment)
    - When it was enabled
    - Why (reason/justification)
    - TTL/expiration
    - Token used (if applicable)
    - Which decisions were affected
    """
    enabled_at: str
    enabled_by: Optional[str] = None
    reason: Optional[str] = None
    expires_at: Optional[str] = None
    token_used: Optional[str] = None
    affected_validators: List[str] = field(default_factory=list)
    affected_decisions: List[str] = field(default_factory=list)  # Decision codes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "enabled_at": self.enabled_at,
            "enabled_by": self.enabled_by,
            "reason": self.reason,
            "expires_at": self.expires_at,
            "token_used": self.token_used,
            "affected_validators": self.affected_validators,
            "affected_decisions": self.affected_decisions,
        }


class PolicyAuditLogger:
    """
    Audit logger for policy changes and breakglass activations
    """
    
    def __init__(self):
        """Initialize audit logger"""
        self.records: List[BreakglassAuditRecord] = []
    
    def log_breakglass_activation(
        self,
        policy: Policy,
        enabled_by: Optional[str] = None,
        reason: Optional[str] = None,
        token_used: Optional[str] = None,
    ) -> BreakglassAuditRecord:
        """
        Log breakglass activation
        
        Args:
            policy: Policy with breakglass override
            enabled_by: Who enabled it (user ID, system, etc.)
            reason: Reason/justification
            token_used: Override token used (if applicable)
            
        Returns:
            Audit record
        """
        override = policy.global_override
        if not override or not override.enabled:
            raise ValueError("Breakglass not enabled in policy")
        
        record = BreakglassAuditRecord(
            enabled_at=datetime.now(timezone.utc).isoformat(),
            enabled_by=enabled_by or "unknown",
            reason=reason,
            expires_at=override.expires_at,
            token_used=token_used,
        )
        
        self.records.append(record)
        return record
    
    def get_breakglass_audit(self, policy: Policy) -> Optional[BreakglassAuditRecord]:
        """
        Get breakglass audit record for policy
        
        Args:
            policy: Policy to check
            
        Returns:
            Latest audit record if breakglass is active, None otherwise
        """
        if not policy.global_override or not policy.global_override.enabled:
            return None
        
        # Return most recent record
        if self.records:
            return self.records[-1]
        
        return None


# Global audit logger instance
_global_audit_logger: Optional[PolicyAuditLogger] = None


def get_audit_logger() -> PolicyAuditLogger:
    """Get global audit logger instance"""
    global _global_audit_logger
    if _global_audit_logger is None:
        _global_audit_logger = PolicyAuditLogger()
    return _global_audit_logger


__all__ = [
    "BreakglassAuditRecord",
    "PolicyAuditLogger",
    "get_audit_logger",
]
