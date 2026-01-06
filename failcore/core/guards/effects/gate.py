# failcore/core/audit/gate.py
"""
Side-Effect Boundary Gate - pre-execution boundary check

This gate performs fast pre-execution checks based on predicted side-effects.
It acts as a "boundary guard" before the main policy check.

Design principle:
- Predict side-effects from tool name and parameters (heuristic)
- Check against boundary (fast check, no execution needed)
- Return PolicyResult if crossing detected
- Main policy still runs after this gate
"""

from typing import List, Optional
from dataclasses import dataclass

from .boundary import SideEffectBoundary
from .side_effect_auditor import SideEffectAuditor
from .side_effects import SideEffectType
from failcore.core.guards.effects.detection import (
    detect_filesystem_side_effect,
    detect_network_side_effect,
    detect_exec_side_effect,
)
from failcore.core.policy.policy import PolicyResult
from failcore.core.types.step import Step, RunContext


@dataclass
class PredictedSideEffect:
    """Predicted side-effect from tool analysis"""
    type: SideEffectType
    target: Optional[str] = None
    confidence: str = "medium"  # "high", "medium", "low"


class SideEffectBoundaryGate:
    """
    Side-effect boundary gate for pre-execution checks
    
    This gate predicts side-effects and checks them against boundaries
    before tool execution. It's fast and deterministic.
    """
    
    def __init__(self, boundary: Optional[SideEffectBoundary] = None):
        """
        Initialize side-effect boundary gate
        
        Args:
            boundary: Side-effect boundary to enforce (None = no enforcement)
        """
        self.boundary = boundary
        self.auditor = SideEffectAuditor(boundary) if boundary else None
    
    def check(
        self,
        step: Step,
        ctx: RunContext,
    ) -> tuple[bool, Optional[PolicyResult], List[PredictedSideEffect]]:
        """
        Check predicted side-effects against boundary
        
        Args:
            step: Step to check
            ctx: Run context
        
        Returns:
            Tuple of:
            - allowed: True if all predicted side-effects are allowed
            - policy_result: PolicyResult if denied, None if allowed
            - predicted_side_effects: List of predicted side-effects
        """
        if not self.auditor:
            # No boundary configured, allow all
            return True, None, []
        
        # Predict side-effects from tool and params
        predicted = self._predict_side_effects(step.tool, step.params)
        
        # Check each predicted side-effect against boundary
        for pred in predicted:
            if self.auditor.check_crossing(pred.type):
                # Boundary crossed - deny
                return False, PolicyResult(
                    allowed=False,
                    reason=f"Predicted side-effect {pred.type.value} would cross boundary",
                    error_code="SIDE_EFFECT_BOUNDARY_CROSSED",
                    suggestion=f"Tool {step.tool} would perform {pred.type.value} on {pred.target or 'unknown target'}, which is not allowed by boundary",
                    details={
                        "predicted_side_effect": pred.type.value,
                        "target": pred.target,
                        "tool": step.tool,
                        "step_id": step.id,
                    },
                ), predicted
        
        # All predicted side-effects are allowed
        return True, None, predicted
    
    def _predict_side_effects(
        self,
        tool: str,
        params: dict,
    ) -> List[PredictedSideEffect]:
        """
        Predict side-effects from tool name and parameters
        
        Args:
            tool: Tool name
            params: Tool parameters
        
        Returns:
            List of predicted side-effects
        """
        predicted = []
        
        # Filesystem side-effects
        fs_read = detect_filesystem_side_effect(tool, params, "read")
        if fs_read:
            predicted.append(PredictedSideEffect(
                type=fs_read,
                target=params.get("path") or params.get("file"),
                confidence="high",
            ))
        
        fs_write = detect_filesystem_side_effect(tool, params, "write")
        if fs_write:
            predicted.append(PredictedSideEffect(
                type=fs_write,
                target=params.get("path") or params.get("file"),
                confidence="high",
            ))
        
        fs_delete = detect_filesystem_side_effect(tool, params, "delete")
        if fs_delete:
            predicted.append(PredictedSideEffect(
                type=fs_delete,
                target=params.get("path") or params.get("file"),
                confidence="high",
            ))
        
        # Network side-effects
        net_egress = detect_network_side_effect(tool, params, "egress")
        if net_egress:
            predicted.append(PredictedSideEffect(
                type=net_egress,
                target=params.get("url") or params.get("host"),
                confidence="high",
            ))
        
        # Exec side-effects
        exec_effect = detect_exec_side_effect(tool, params)
        if exec_effect:
            predicted.append(PredictedSideEffect(
                type=exec_effect,
                target=params.get("command") or params.get("cmd"),
                confidence="high",
            ))
        
        return predicted


__all__ = [
    "SideEffectBoundaryGate",
    "PredictedSideEffect",
]
