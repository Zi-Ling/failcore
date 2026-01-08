"""
HITL Approval Plane - Middleware

Integrate approval flow into execution pipeline
"""

from typing import Any, Dict, Optional
from .models import ApprovalRequest, ApprovalStatus, RiskLevel
from .store import ApprovalStore
from .resolver import ApprovalResolver


class ApprovalMiddleware:
    """
    Approval middleware for Executor/ToolRuntime
    
    Integration flow:
    1. After policy check, if high-risk operation detected
    2. Create ApprovalRequest and save to store
    3. Wait for human decision (blocking or async)
    4. If approved: continue execution
    5. If rejected: raise APPROVAL_REJECTED error
    6. All actions logged to trace + receipt
    """
    
    def __init__(
        self,
        store: ApprovalStore = None,
        require_approval_for: set[RiskLevel] = None,
        auto_approve_low_risk: bool = False,
        default_timeout_s: int = 300,
    ):
        self.store = store or ApprovalStore()
        self.resolver = ApprovalResolver(self.store)
        self.require_approval_for = require_approval_for or {RiskLevel.HIGH, RiskLevel.CRITICAL}
        self.auto_approve_low_risk = auto_approve_low_risk
        self.default_timeout_s = default_timeout_s
    
    def should_require_approval(
        self,
        tool_name: str,
        params: Dict[str, Any],
        risk_level: RiskLevel,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Decide if operation requires approval
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            risk_level: Risk level from policy
            metadata: Additional metadata (e.g., tool risk/effect tags)
        
        Returns:
            True if requires approval
        """
        # Check risk level
        if risk_level in self.require_approval_for:
            return True
        
        # Check tool metadata (e.g., high-risk tool)
        if metadata and metadata.get("risk") == "high":
            return True
        
        return False
    
    def create_approval_request(
        self,
        run_id: str,
        step_id: str,
        tool_name: str,
        params: Dict[str, Any],
        risk_level: RiskLevel,
        risk_reason: str,
        trace_id: str = None,
        context: Dict[str, Any] = None,
    ) -> ApprovalRequest:
        """
        Create approval request for high-risk operation
        
        Args:
            run_id: Run ID
            step_id: Step ID
            tool_name: Tool name
            params: Tool parameters (will be sanitized)
            risk_level: Risk level
            risk_reason: Why this is risky
            trace_id: Trace ID for correlation
            context: Additional context
        
        Returns:
            ApprovalRequest
        """
        import uuid
        
        # Sanitize params (remove sensitive data)
        params_summary = self._sanitize_params(params)
        
        request = ApprovalRequest(
            request_id=f"approval_{uuid.uuid4().hex[:16]}",
            run_id=run_id,
            step_id=step_id,
            trace_id=trace_id,
            tool_name=tool_name,
            params_summary=params_summary,
            risk_level=risk_level,
            risk_reason=risk_reason,
            timeout_seconds=self.default_timeout_s,
            context=context or {},
        )
        
        # Save to store
        self.store.save(request)
        
        return request
    
    def _sanitize_params(self, params: Dict[str, Any], max_len: int = 100) -> Dict[str, Any]:
        """
        Sanitize parameters for display
        
        - Truncate long values
        - Mask sensitive keys (password, token, secret, key)
        """
        sanitized = {}
        sensitive_keys = {"password", "token", "secret", "key", "api_key", "auth"}
        
        for key, value in params.items():
            # Mask sensitive keys
            if any(sk in key.lower() for sk in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            else:
                # Truncate long values
                value_str = str(value)
                if len(value_str) > max_len:
                    sanitized[key] = value_str[:max_len] + "..."
                else:
                    sanitized[key] = value
        
        return sanitized
    
    def wait_for_approval(
        self,
        request: ApprovalRequest,
        on_poll: Optional[callable] = None
    ) -> ApprovalRequest:
        """
        Wait for human approval decision
        
        Args:
            request: Approval request
            on_poll: Optional callback for progress updates
        
        Returns:
            Resolved ApprovalRequest
        """
        # Try auto-approval first
        if self.resolver.auto_approve_if_trusted(request, auto_approve_low_risk=self.auto_approve_low_risk):
            return request
        
        # Wait for human decision (blocking)
        return self.resolver.wait_for_decision(request, on_poll=on_poll)
    
    def handle_decision(self, request: ApprovalRequest) -> bool:
        """
        Handle approval decision
        
        Args:
            request: Resolved approval request
        
        Returns:
            True if approved, False if rejected
        
        Raises:
            Exception if rejected (to stop execution)
        """
        if request.is_approved():
            return True
        
        elif request.is_rejected():
            from failcore.core.errors import FailCoreError, codes
            raise FailCoreError(
                message=f"Operation rejected by {request.decided_by}: {request.decision_reason}",
                error_code=codes.APPROVAL_REJECTED,
                phase="APPROVAL",
                suggestion=f"Contact approver for clarification: {request.decided_by}",
                details={
                    "request_id": request.request_id,
                    "decided_by": request.decided_by,
                    "decision_reason": request.decision_reason,
                }
            )
        
        elif request.status == ApprovalStatus.EXPIRED:
            from failcore.core.errors import FailCoreError, codes
            raise FailCoreError(
                message=f"Approval timeout: no decision after {request.timeout_seconds}s",
                error_code=codes.APPROVAL_TIMEOUT,
                phase="APPROVAL",
                suggestion=f"Retry with longer timeout or contact administrator",
                details={
                    "request_id": request.request_id,
                    "timeout_seconds": request.timeout_seconds,
                }
            )
        
        return False


__all__ = ["ApprovalMiddleware"]
