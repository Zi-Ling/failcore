# failcore/core/approval/resolver.py
"""
HITL Approval Plane - Resolver

Resolve approval requests: wait for decision, timeout handling
"""

import time
from typing import Optional, Callable
from datetime import datetime, timezone
from .models import ApprovalRequest, ApprovalStatus
from .store import ApprovalStore


class ApprovalResolver:
    """
    Resolve approval requests
    
    Supports:
    - Wait for human decision (blocking or async)
    - Timeout handling
    - Decision callbacks
    """
    
    def __init__(self, store: ApprovalStore):
        self.store = store
    
    def wait_for_decision(
        self,
        request: ApprovalRequest,
        poll_interval_s: float = 1.0,
        on_poll: Optional[Callable[[ApprovalRequest], None]] = None
    ) -> ApprovalRequest:
        """
        Wait for human decision (blocking)
        
        Args:
            request: Approval request
            poll_interval_s: Polling interval in seconds
            on_poll: Optional callback called on each poll (for progress updates)
        
        Returns:
            Updated ApprovalRequest with decision
        """
        start_time = datetime.now(timezone.utc)
        
        while request.is_pending():
            # Check timeout
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(request.requested_at.replace('Z', '+00:00'))).total_seconds()
            if elapsed >= request.timeout_seconds:
                # Timeout - auto-reject
                request.expire()
                self.store.update(request)
                break
            
            # Poll for update
            time.sleep(poll_interval_s)
            
            # Reload from store (human may have updated)
            updated = self.store.load(request.request_id, request.run_id)
            if updated:
                request = updated
            
            # Callback for progress updates (e.g., emit event)
            if on_poll:
                on_poll(request)
        
        return request
    
    def check_decision(self, request_id: str, run_id: str = None) -> Optional[ApprovalRequest]:
        """
        Check current decision status (non-blocking)
        
        Returns:
            ApprovalRequest if decision made, None if still pending
        """
        request = self.store.load(request_id, run_id)
        if not request:
            return None
        
        if request.is_pending():
            return None  # Still waiting
        
        return request
    
    def auto_approve_if_trusted(
        self,
        request: ApprovalRequest,
        trusted_users: set[str] = None,
        auto_approve_low_risk: bool = False
    ) -> bool:
        """
        Auto-approve based on trust rules
        
        Args:
            request: Approval request
            trusted_users: Set of trusted user IDs (auto-approve their requests)
            auto_approve_low_risk: Auto-approve low/medium risk
        
        Returns:
            True if auto-approved, False otherwise
        """
        from .models import RiskLevel
        
        # Auto-approve low risk if enabled
        if auto_approve_low_risk and request.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            request.approve(
                approved_by="system:auto_approve",
                reason=f"Auto-approved: risk level {request.risk_level.value}"
            )
            self.store.update(request)
            return True
        
        # Trusted users (if implemented in context)
        if trusted_users and request.context.get("user_id") in trusted_users:
            request.approve(
                approved_by="system:trusted_user",
                reason=f"Auto-approved: trusted user {request.context.get('user_id')}"
            )
            self.store.update(request)
            return True
        
        return False


__all__ = ["ApprovalResolver"]
