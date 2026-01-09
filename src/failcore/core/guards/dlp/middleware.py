"""
DLP Middleware

Data Loss Prevention middleware for tool call boundaries

NOTE: This is preflight gate implementation. For unified gate interface, use:
    from failcore.core.gate import PreflightGate
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Callable

from .policies import DLPAction, DLPPolicy, PolicyMatrix
from .patterns import DLPPatternRegistry
from ..taint.tag import TaintTag, DataSensitivity, TaintSource
from ..taint.context import TaintContext
from ..taint.sanitizer import DataSanitizer


class DLPMiddleware:
    """
    Data Loss Prevention middleware
    
    Intercepts tool calls to prevent sensitive data leakage
    
    Integration flow:
    1. on_call_start: Check if data sink is receiving tainted data
    2. Apply DLP policy based on data sensitivity
    3. BLOCK / SANITIZE / WARN / REQUIRE_APPROVAL
    4. Log all actions to trace
    """
    
    def __init__(
        self,
        taint_context: Optional[TaintContext] = None,
        sanitizer: Optional[DataSanitizer] = None,
        pattern_registry: Optional[DLPPatternRegistry] = None,
        policy_matrix: Optional[PolicyMatrix] = None,
        strict_mode: bool = True,
        enabled: bool = True,
    ):
        """
        Initialize DLP middleware
        
        Args:
            taint_context: Taint tracking context
            sanitizer: Data sanitizer
            pattern_registry: DLP pattern registry
            policy_matrix: DLP policy matrix
            strict_mode: Use strict policy matrix
            enabled: Enable DLP checks
        """
        self.taint_context = taint_context or TaintContext()
        self.sanitizer = sanitizer or DataSanitizer()
        self.pattern_registry = pattern_registry or DLPPatternRegistry()
        self.policy_matrix = policy_matrix or PolicyMatrix(strict_mode=strict_mode)
        self.enabled = enabled
    
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
        if not self.enabled:
            return None
        
        step_id = context.get("step_id", "")
        run_id = context.get("run_id", "")
        
        # Check if this is a data sink
        if not self.taint_context.is_sink_tool(tool_name):
            return None
        
        # Detect tainted inputs
        dependencies = context.get("dependencies", [])
        taint_tags = self.taint_context.detect_tainted_inputs(params, dependencies)
        
        if not taint_tags:
            return None
        
        # Data leakage risk detected
        return self._handle_data_leakage(
            tool_name,
            params,
            taint_tags,
            context,
            emit
        )
    
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
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            taint_tags: Detected taint tags
            context: Execution context
            emit: Event emitter
        
        Returns:
            Sanitized params or None
        
        Raises:
            FailCoreError if blocked
        """
        # Determine max sensitivity
        max_sensitivity = self._get_max_sensitivity(taint_tags)
        
        # Get DLP policy
        policy = self.policy_matrix.get_policy(max_sensitivity)
        
        # Emit DLP event
        if emit:
            emit({
                "type": "DLP_LEAKAGE_DETECTED",
                "tool": tool_name,
                "sensitivity": max_sensitivity.value,
                "action": policy.action.value,
                "taint_sources": list(set(tag.source.value for tag in taint_tags)),
                "step_id": context.get("step_id", ""),
            })
        
        # Execute DLP action
        if policy.action == DLPAction.BLOCK:
            return self._block_leakage(tool_name, taint_tags, max_sensitivity, policy, context)
        
        elif policy.action == DLPAction.SANITIZE:
            return self._sanitize_params(tool_name, params, taint_tags, policy, emit)
        
        elif policy.action == DLPAction.REQUIRE_APPROVAL:
            return self._require_approval(tool_name, params, taint_tags, max_sensitivity, context)
        
        elif policy.action == DLPAction.WARN:
            self._warn_leakage(tool_name, taint_tags, max_sensitivity, emit)
            return None
        
        # ALLOW
        return None
    
    def _get_max_sensitivity(self, taint_tags: set) -> DataSensitivity:
        """
        Get maximum sensitivity from taint tags
        
        Args:
            taint_tags: Taint tags
        
        Returns:
            Maximum sensitivity level
        """
        if not taint_tags:
            return DataSensitivity.INTERNAL
        
        # Sensitivity hierarchy
        hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.PII: 3,
            DataSensitivity.SECRET: 4,
        }
        
        max_level = max(hierarchy.get(tag.sensitivity, 1) for tag in taint_tags)
        
        for sensitivity, level in hierarchy.items():
            if level == max_level:
                return sensitivity
        
        return DataSensitivity.INTERNAL
    
    def _block_leakage(
        self,
        tool_name: str,
        taint_tags: set,
        sensitivity: DataSensitivity,
        policy: DLPPolicy,
        context: Dict[str, Any],
    ) -> None:
        """
        Block operation - raise error
        
        Args:
            tool_name: Tool name
            taint_tags: Taint tags
            sensitivity: Data sensitivity
            policy: DLP policy
            context: Execution context
        
        Raises:
            FailCoreError
        """
        from failcore.core.errors import FailCoreError, codes
        
        sources = ", ".join(set(tag.source.value for tag in taint_tags))
        
        raise FailCoreError(
            message=f"DLP: {sensitivity.value} data from {sources} blocked from {tool_name}",
            error_code=codes.DATA_LEAK_PREVENTED,
            phase="DLP_CHECK",
            suggestion=policy.reason or f"Sanitize data before sending to {tool_name}",
            details={
                "tool": tool_name,
                "sensitivity": sensitivity.value,
                "sources": sources,
                "taint_count": len(taint_tags),
                "policy_action": policy.action.value,
            }
        )
    
    def _sanitize_params(
        self,
        tool_name: str,
        params: Dict[str, Any],
        taint_tags: set,
        policy: DLPPolicy,
        emit: Optional[Callable],
    ) -> Dict[str, Any]:
        """
        Sanitize parameters before execution
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            taint_tags: Taint tags
            policy: DLP policy
            emit: Event emitter
        
        Returns:
            Sanitized parameters
        """
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
        sensitivity: DataSensitivity,
        context: Dict[str, Any],
    ) -> None:
        """
        Require human approval
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            taint_tags: Taint tags
            sensitivity: Data sensitivity
            context: Execution context
        
        Raises:
            FailCoreError (approval required)
        """
        from failcore.core.errors import FailCoreError, codes
        
        sources = ", ".join(set(tag.source.value for tag in taint_tags))
        
        raise FailCoreError(
            message=f"DLP: Approval required for {sensitivity.value} data from {sources} to {tool_name}",
            error_code=codes.APPROVAL_REQUIRED,
            phase="DLP_APPROVAL",
            suggestion="Contact data governance team for approval",
            details={
                "tool": tool_name,
                "sources": sources,
                "sensitivity": sensitivity.value,
                "requires_approval": True,
            }
        )
    
    def _warn_leakage(
        self,
        tool_name: str,
        taint_tags: set,
        sensitivity: DataSensitivity,
        emit: Optional[Callable],
    ) -> None:
        """
        Emit warning for data leakage
        
        Args:
            tool_name: Tool name
            taint_tags: Taint tags
            sensitivity: Data sensitivity
            emit: Event emitter
        """
        if emit:
            sources = ", ".join(set(tag.source.value for tag in taint_tags))
            emit({
                "type": "DLP_WARNING",
                "tool": tool_name,
                "sensitivity": sensitivity.value,
                "sources": sources,
                "message": f"Warning: {sensitivity.value} data from {sources} sent to {tool_name}",
            })


__all__ = ["DLPMiddleware"]
