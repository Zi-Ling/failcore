"""
Taint Tracking - Taint Middleware

Lightweight taint tracking at tool boundaries for marking and propagation.
This middleware is responsible ONLY for marking data sources and tracking taint propagation.

NOTE: For DLP policy enforcement, use DLPMiddleware from guards.dlp.middleware.
This middleware should be called BEFORE DLPMiddleware to mark taint, then DLP
can use taint context to make policy decisions.

Call order: TaintMiddleware (mark) -> DLPMiddleware (enforce policy)
"""

from typing import Dict, Any, Optional, Callable
from enum import Enum
from .tag import TaintTag, TaintSource, DataSensitivity
from .context import TaintContext
from .sanitizer import DataSanitizer


class DLPAction(str, Enum):
    """DLP policy actions (kept for backward compatibility, but use guards.dlp.policies.DLPAction)"""
    ALLOW = "allow"              # Allow operation
    BLOCK = "block"              # Block operation
    SANITIZE = "sanitize"        # Sanitize data before operation
    REQUIRE_APPROVAL = "require_approval"  # Require human approval


class TaintMiddleware:
    """
    Taint tracking middleware
    
    Responsibilities:
    - Mark data sources (source tools) as tainted
    - Track taint propagation through tool calls
    - Provide taint context for DLP policy enforcement
    
    Integration flow:
    1. on_call_start (source tool): Mark output as tainted in context
    2. on_call_success (source tool): Record taint tags for outputs
    3. on_call_start (sink tool): Provide taint context (DLP middleware uses this)
    
    NOTE: This middleware does NOT enforce DLP policies. It only tracks taint.
    For policy enforcement, use DLPMiddleware from guards.dlp.middleware.
    """
    
    def __init__(
        self,
        taint_context: TaintContext = None,
        sanitizer: DataSanitizer = None,
        strict_mode: bool = True,
    ):
        """
        Args:
            taint_context: Taint tracking context
            sanitizer: Data sanitizer
            strict_mode: If True, block all tainted->sink flows by default
        """
        self.taint_context = taint_context or TaintContext()
        self.sanitizer = sanitizer or DataSanitizer()
        self.strict_mode = strict_mode
        
        # DLP policy matrix: sensitivity -> action
        self.policy_matrix = {
            DataSensitivity.PUBLIC: DLPAction.ALLOW,
            DataSensitivity.INTERNAL: DLPAction.SANITIZE if strict_mode else DLPAction.ALLOW,
            DataSensitivity.CONFIDENTIAL: DLPAction.REQUIRE_APPROVAL if not strict_mode else DLPAction.BLOCK,
            DataSensitivity.PII: DLPAction.BLOCK,
            DataSensitivity.SECRET: DLPAction.BLOCK,
        }
    
    def on_call_start(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        emit: Optional[Callable] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Called before tool execution
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            context: Execution context
            emit: Event emitter
        
        Returns:
            Modified params (if sanitized) or None
        
        Raises:
            FailCoreError if DLP policy blocks operation
        """
        step_id = context.get("step_id", "")
        run_id = context.get("run_id", "")
        
        # Check if this is a data sink
        if self.taint_context.is_sink_tool(tool_name):
            # Detect tainted inputs
            dependencies = context.get("dependencies", [])
            taint_tags = self.taint_context.detect_tainted_inputs(params, dependencies)
            
            if taint_tags:
                # Data leakage risk detected
                return self._handle_data_leakage(
                    tool_name,
                    params,
                    taint_tags,
                    context,
                    emit
                )
        
        # Check if this is a data source
        if self.taint_context.is_source_tool(tool_name):
            # Will mark as tainted in on_call_success
            if emit:
                emit({
                    "type": "DATA_SOURCE_DETECTED",
                    "tool": tool_name,
                    "step_id": step_id,
                })
        
        return None
    
    def _handle_data_leakage(
        self,
        tool_name: str,
        params: Dict[str, Any],
        taint_tags: set,
        context: Dict[str, Any],
        emit: Optional[Callable],
    ) -> Optional[Dict[str, Any]]:
        """
        Handle detected data leakage risk
        
        Returns:
            Sanitized params or None
        
        Raises:
            FailCoreError if blocked
        """
        # Determine max sensitivity
        max_sensitivity = max(
            (tag.sensitivity for tag in taint_tags),
            key=lambda s: list(DataSensitivity).index(s)
        )
        
        # Get DLP action
        dlp_action = self.policy_matrix.get(max_sensitivity, DLPAction.BLOCK)
        
        # Emit DLP event
        if emit:
            emit({
                "type": "DLP_LEAKAGE_DETECTED",
                "tool": tool_name,
                "sensitivity": max_sensitivity.value,
                "action": dlp_action.value,
                "taint_sources": [tag.source.value for tag in taint_tags],
            })
        
        # Execute DLP action
        if dlp_action == DLPAction.BLOCK:
            return self._block_leakage(tool_name, taint_tags, max_sensitivity, context)
        
        elif dlp_action == DLPAction.SANITIZE:
            return self._sanitize_params(tool_name, params, taint_tags, emit)
        
        elif dlp_action == DLPAction.REQUIRE_APPROVAL:
            return self._require_approval(tool_name, params, taint_tags, context)
        
        # ALLOW
        return None
    
    def _block_leakage(
        self,
        tool_name: str,
        taint_tags: set,
        sensitivity: DataSensitivity,
        context: Dict[str, Any],
    ) -> None:
        """Block operation - raise error"""
        from failcore.core.errors import FailCoreError, codes
        
        sources = ", ".join(set(tag.source.value for tag in taint_tags))
        
        raise FailCoreError(
            message=f"Data leakage prevented: {sensitivity.value} data from {sources} cannot be sent to {tool_name}",
            error_code=codes.DATA_LEAK_PREVENTED,
            phase="DLP_CHECK",
            suggestion=f"Sanitize data before sending, or use internal-only tools. Data sources: {sources}",
            details={
                "tool": tool_name,
                "sensitivity": sensitivity.value,
                "sources": sources,
                "taint_count": len(taint_tags),
            }
        )
    
    def _sanitize_params(
        self,
        tool_name: str,
        params: Dict[str, Any],
        taint_tags: set,
        emit: Optional[Callable],
    ) -> Dict[str, Any]:
        """Sanitize parameters before execution"""
        # Check what needs sanitization
        needs_pii_mask = any(tag.contains_pii for tag in taint_tags)
        needs_secret_mask = any(tag.contains_secrets for tag in taint_tags)
        
        # Sanitize
        sanitized_params = self.sanitizer.sanitize(
            params,
            mask_pii=needs_pii_mask,
            mask_secrets=needs_secret_mask,
        )
        
        if emit:
            emit({
                "type": "DLP_SANITIZED",
                "tool": tool_name,
                "pii_masked": needs_pii_mask,
                "secrets_masked": needs_secret_mask,
            })
        
        return sanitized_params
    
    def _require_approval(
        self,
        tool_name: str,
        params: Dict[str, Any],
        taint_tags: set,
        context: Dict[str, Any],
    ) -> None:
        """Require human approval (integrate with ApprovalMiddleware)"""
        from failcore.core.errors import FailCoreError, codes
        
        # For now, block and suggest approval
        # Production: integrate with ApprovalMiddleware
        sources = ", ".join(set(tag.source.value for tag in taint_tags))
        
        raise FailCoreError(
            message=f"Approval required: Sensitive data from {sources} requires approval before sending to {tool_name}",
            error_code=codes.APPROVAL_REQUIRED,
            phase="DLP_APPROVAL",
            suggestion="Contact data governance team for approval, or use data sanitization",
            details={
                "tool": tool_name,
                "sources": sources,
                "requires_approval": True,
            }
        )
    
    def on_call_success(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        result: Any,
        emit: Optional[Callable] = None,
    ) -> None:
        """
        Called after successful tool execution
        
        Mark source tool outputs as tainted
        """
        if self.taint_context.is_source_tool(tool_name):
            step_id = context.get("step_id", "")
            
            # Determine source type
            source = self._infer_source_type(tool_name)
            
            # Detect sensitivity
            sensitivity = self._infer_sensitivity(tool_name, result)
            
            # Create taint tag
            tag = TaintTag(
                source=source,
                source_tool=tool_name,
                source_step_id=step_id,
                sensitivity=sensitivity,
                contains_pii=self._contains_pii(result),
                contains_secrets=self._contains_secrets(tool_name),
                reason=f"Data from {source.value} source",
            )
            
            # Mark as tainted
            self.taint_context.mark_tainted(step_id, tag)
            
            if emit:
                emit({
                    "type": "DATA_TAINTED",
                    "tool": tool_name,
                    "step_id": step_id,
                    "source": source.value,
                    "sensitivity": sensitivity.value,
                })
    
    def _infer_source_type(self, tool_name: str) -> TaintSource:
        """Infer taint source from tool name"""
        if "file" in tool_name.lower():
            return TaintSource.FILE
        elif "db" in tool_name.lower() or "database" in tool_name.lower():
            return TaintSource.DATABASE
        elif "api" in tool_name.lower() or "http" in tool_name.lower():
            return TaintSource.API
        elif "secret" in tool_name.lower() or "credential" in tool_name.lower():
            return TaintSource.SECRET
        elif "env" in tool_name.lower():
            return TaintSource.ENVIRONMENT
        else:
            return TaintSource.USER_INPUT
    
    def _infer_sensitivity(self, tool_name: str, result: Any) -> DataSensitivity:
        """Infer data sensitivity"""
        # Check tool name for hints
        if "secret" in tool_name.lower() or "password" in tool_name.lower():
            return DataSensitivity.SECRET
        
        if "customer" in tool_name.lower() or "user" in tool_name.lower():
            return DataSensitivity.PII
        
        # Check result content
        if isinstance(result, (str, dict, list)):
            patterns = self.sanitizer.detect_sensitive_patterns(result)
            if any(p in patterns for p in ["email", "phone", "ssn", "credit_card"]):
                return DataSensitivity.PII
            if any(p in patterns for p in ["api_key", "token", "password"]):
                return DataSensitivity.SECRET
        
        return DataSensitivity.INTERNAL
    
    def _contains_pii(self, result: Any) -> bool:
        """Check if result contains PII"""
        if isinstance(result, (str, dict, list)):
            patterns = self.sanitizer.detect_sensitive_patterns(result)
            return any(p in patterns for p in ["email", "phone", "ssn", "credit_card"])
        return False
    
    def _contains_secrets(self, tool_name: str) -> bool:
        """Check if tool deals with secrets"""
        return any(keyword in tool_name.lower() for keyword in ["secret", "password", "token", "key", "credential"])


# Backward compatibility alias (deprecated, use guards.dlp.middleware.DLPMiddleware)
DLPMiddleware = TaintMiddleware

__all__ = ["TaintMiddleware", "DLPAction", "DLPMiddleware"]  # DLPMiddleware for backward compatibility
