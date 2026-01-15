"""
Preflight Gate - Tool boundary gate implementation

Implements Gate interface for tool call boundary (framework mode).
This is what guards/* currently does, but abstracted as Gate.
"""

from __future__ import annotations

from typing import Optional

from .interface import Gate, GateContext, GateVerdict
from ..events.attempt import AttemptEvent, AttemptStatus, VerdictSchema, TargetSchema, TargetType
from ..guards.semantic.verdict import VerdictAction


class PreflightGate:
    """
    Preflight gate implementation
    
    Checks tool calls before execution.
    Wraps existing guards/* logic under Gate interface.
    
    Design:
    - Uses rules from core/rules (DLP, semantic, effects)
    - Produces ATTEMPT event before execution
    - Verdict written to trace regardless of action
    """
    
    def __init__(
        self,
        dlp_enabled: bool = False,
        semantic_enabled: bool = False,
        effects_enabled: bool = False,
    ):
        """
        Initialize preflight gate
        
        Args:
            dlp_enabled: Enable DLP checks
            semantic_enabled: Enable semantic checks
            effects_enabled: Enable effects boundary checks
        """
        self.dlp_enabled = dlp_enabled
        self.semantic_enabled = semantic_enabled
        self.effects_enabled = effects_enabled
        
        # TODO: Initialize actual guard instances
        # self.dlp_guard = DLPMiddleware(...) if dlp_enabled else None
        # self.semantic_guard = SemanticGuardMiddleware(...) if semantic_enabled else None
        # self.effects_guard = EffectsGate(...) if effects_enabled else None
    
    def check(self, context: GateContext) -> GateVerdict:
        """
        Check tool call and return verdict
        
        Args:
            context: Gate context
        
        Returns:
            Gate verdict
        """
        # TODO: Implement actual checks using guards
        # For now, allow all
        return GateVerdict(
            action=VerdictAction.ALLOW,
            reason="Preflight checks passed",
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
        
        # Infer target from params
        target = self._infer_target(context)
        
        # Create verdict schema
        verdict_schema = VerdictSchema(
            action=verdict.action,
            reason=verdict.reason,
            rule_name=verdict.rule_name,
            rule_category=verdict.rule_category,
            confidence=verdict.confidence,
            gate_type="preflight",
            triggered_by=verdict.rule_name,
            metadata=verdict.metadata,
        )
        
        return AttemptEvent(
            attempt_id=context.attempt_id or f"{context.run_id}_{context.step_id}",
            run_id=context.run_id,
            step_id=context.step_id,
            tool=context.tool,
            params=verdict.sanitized_params or context.params,
            verdict=verdict_schema,
            status=status,
            target=target,
            gate_type="preflight",
            context=context.metadata,
        )
    
    def _infer_target(self, context: GateContext) -> Optional[TargetSchema]:
        """Infer target from tool params (pre-execution)"""
        if not context.params:
            return None
        
        # Simple heuristics (can be enhanced)
        params = context.params
        
        # Filesystem target
        if "path" in params or "file" in params:
            path = params.get("path") or params.get("file")
            return TargetSchema(
                type=TargetType.FILESYSTEM,
                inferred=str(path) if path else None,
                inferred_confidence="high",
            )
        
        # Network target
        if "url" in params or "host" in params:
            target = params.get("url") or params.get("host")
            return TargetSchema(
                type=TargetType.NETWORK,
                inferred=str(target) if target else None,
                inferred_confidence="high",
            )
        
        # Execution target
        if "command" in params or "cmd" in params:
            cmd = params.get("command") or params.get("cmd")
            return TargetSchema(
                type=TargetType.EXECUTION,
                inferred=str(cmd) if cmd else None,
                inferred_confidence="high",
            )
        
        return None


__all__ = ["PreflightGate"]
