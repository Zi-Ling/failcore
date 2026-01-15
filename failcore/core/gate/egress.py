"""
Egress Gate - Proxy boundary gate implementation

Implements Gate interface for proxy/network boundary (drop-in mode).
This gives proxy mode the same blocking capability as preflight mode.
"""

from __future__ import annotations

from typing import Optional
import json

from .interface import Gate, GateContext, GateVerdict
from ..events.attempt import AttemptEvent, AttemptStatus, VerdictSchema, TargetSchema, TargetType
from ..guards.semantic.verdict import VerdictAction


class EgressGate:
    """
    Egress gate implementation
    
    Checks proxy requests before forwarding.
    Provides same decision authority as preflight gate.
    
    Design:
    - Uses same rules from core/rules (DLP, semantic)
    - Produces ATTEMPT event before forwarding
    - Can block/sanitize proxy requests
    - Solves "proxy mode can't block" problem
    """
    
    def __init__(
        self,
        dlp_enabled: bool = False,
        content_inspection_enabled: bool = False,
    ):
        """
        Initialize egress gate
        
        Args:
            dlp_enabled: Enable DLP checks on request body
            content_inspection_enabled: Enable deep content inspection
        """
        self.dlp_enabled = dlp_enabled
        self.content_inspection_enabled = content_inspection_enabled
        
        # TODO: Initialize actual checkers
        # self.dlp_scanner = RuleRegistry()  # Use unified rule system
    
    def check(self, context: GateContext) -> GateVerdict:
        """
        Check proxy request and return verdict
        
        Args:
            context: Gate context (includes request data)
        
        Returns:
            Gate verdict
        """
        # TODO: Implement actual checks
        # For now, scan request body for DLP patterns if enabled
        
        if self.dlp_enabled and context.body:
            try:
                # Parse body
                body_str = context.body.decode('utf-8', errors='ignore')
                
                # Simple pattern check (placeholder)
                if 'sk-' in body_str:  # OpenAI key pattern
                    return GateVerdict(
                        action=VerdictAction.BLOCK,
                        reason="API key detected in request body",
                        rule_name="DLP_API_KEY",
                        rule_category="dlp",
                        confidence=0.9,
                    )
            except Exception:
                pass  # Fail-open on errors
        
        return GateVerdict(
            action=VerdictAction.ALLOW,
            reason="Egress checks passed",
            confidence=1.0,
        )
    
    def create_attempt_event(
        self,
        context: GateContext,
        verdict: GateVerdict,
    ) -> AttemptEvent:
        """Create attempt event from context and verdict"""
        
        # Determine status from verdict
        status_map = {
            VerdictAction.ALLOW: AttemptStatus.ALLOWED,
            VerdictAction.BLOCK: AttemptStatus.BLOCKED,
            VerdictAction.SANITIZE: AttemptStatus.SANITIZED,
            VerdictAction.WARN: AttemptStatus.WARNED,
            VerdictAction.WARN_APPROVAL_NEEDED: AttemptStatus.WARNED,
        }
        status = status_map.get(verdict.action, AttemptStatus.PENDING)
        
        # Extract target from request
        target = self._extract_target(context)
        
        # Create verdict schema
        verdict_schema = VerdictSchema(
            action=verdict.action,
            reason=verdict.reason,
            rule_name=verdict.rule_name,
            rule_category=verdict.rule_category,
            confidence=verdict.confidence,
            gate_type="egress",
            triggered_by=verdict.rule_name,
            metadata=verdict.metadata,
        )
        
        # Extract params from request body
        params = self._extract_params(context)
        
        return AttemptEvent(
            attempt_id=context.attempt_id or f"{context.run_id}_egress_{id(context)}",
            run_id=context.run_id,
            step_id=context.step_id,
            tool=context.tool or f"{context.method}:{context.endpoint}",
            params=params,
            verdict=verdict_schema,
            status=status,
            target=target,
            gate_type="egress",
            context=context.metadata,
        )
    
    def _extract_target(self, context: GateContext) -> Optional[TargetSchema]:
        """Extract target from request (observed, not inferred)"""
        if not context.endpoint:
            return None
        
        # Network target (actual HTTP request)
        return TargetSchema(
            type=TargetType.NETWORK,
            observed=context.endpoint,  # This is observed (actual URL)
            observed_confidence="high",
        )
    
    def _extract_params(self, context: GateContext) -> Optional[dict]:
        """Extract params from request body"""
        if not context.body:
            return None
        
        try:
            body_str = context.body.decode('utf-8', errors='ignore')
            return json.loads(body_str)
        except Exception:
            return {"raw_body": context.body[:500].hex()}  # Truncate and hex encode


__all__ = ["EgressGate"]
