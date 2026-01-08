"""
HITL Approval Plane - Models

Interactive execution governance: high-risk operations require human approval
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum


class ApprovalStatus(str, Enum):
    """Approval request status"""
    PENDING = "pending"      # Waiting for human decision
    APPROVED = "approved"    # Approved by human
    REJECTED = "rejected"    # Rejected by human
    EXPIRED = "expired"      # Timeout without decision
    CANCELLED = "cancelled"  # Cancelled by system


class RiskLevel(str, Enum):
    """Risk level classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalRequest:
    """
    Approval request for high-risk operations
    
    When Policy identifies high-risk operation, instead of blocking,
    create ApprovalRequest and wait for human decision.
    """
    # Identity (required fields first)
    request_id: str
    run_id: str
    step_id: str
    tool_name: str
    
    # Optional identity
    trace_id: Optional[str] = None
    
    # Operation details
    params_summary: Dict[str, Any] = field(default_factory=dict)  # Sanitized params
    risk_level: RiskLevel = RiskLevel.HIGH
    risk_reason: str = ""
    
    # Approval state
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None  # user_id / email
    decision_reason: Optional[str] = None
    
    # Timeout
    timeout_seconds: int = 300  # 5 minutes default
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)  # Additional info for decision
    
    def approve(self, approved_by: str, reason: str = "") -> None:
        """Approve request"""
        self.status = ApprovalStatus.APPROVED
        self.decided_at = datetime.now(timezone.utc).isoformat()
        self.decided_by = approved_by
        self.decision_reason = reason
    
    def reject(self, rejected_by: str, reason: str) -> None:
        """Reject request"""
        self.status = ApprovalStatus.REJECTED
        self.decided_at = datetime.now(timezone.utc).isoformat()
        self.decided_by = rejected_by
        self.decision_reason = reason
    
    def expire(self) -> None:
        """Mark as expired (timeout)"""
        self.status = ApprovalStatus.EXPIRED
        self.decided_at = datetime.now(timezone.utc).isoformat()
        self.decision_reason = f"Timeout after {self.timeout_seconds}s without decision"
    
    def is_pending(self) -> bool:
        """Check if still waiting for decision"""
        return self.status == ApprovalStatus.PENDING
    
    def is_approved(self) -> bool:
        """Check if approved"""
        return self.status == ApprovalStatus.APPROVED
    
    def is_rejected(self) -> bool:
        """Check if rejected"""
        return self.status == ApprovalStatus.REJECTED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage/serialization"""
        return {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "trace_id": self.trace_id,
            "tool_name": self.tool_name,
            "params_summary": self.params_summary,
            "risk_level": self.risk_level.value,
            "risk_reason": self.risk_reason,
            "status": self.status.value,
            "requested_at": self.requested_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "decision_reason": self.decision_reason,
            "timeout_seconds": self.timeout_seconds,
            "context": self.context,
        }


__all__ = [
    "ApprovalRequest",
    "ApprovalStatus",
    "RiskLevel",
]
