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

from typing import List, Optional, Any
from dataclasses import dataclass

from .boundary import SideEffectBoundary
from .side_effect_auditor import SideEffectAuditor
from .side_effects import SideEffectType, SideEffectCategory
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
    
    def __init__(self, boundary: Optional[SideEffectBoundary] = None, tool_provider: Optional[Any] = None):
        """
        Initialize side-effect boundary gate
        
        Args:
            boundary: Side-effect boundary to enforce (None = no enforcement)
            tool_provider: Optional tool provider to access tool metadata for better prediction
        """
        self.boundary = boundary
        self.auditor = SideEffectAuditor(boundary) if boundary else None
        self.tool_provider = tool_provider
    
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
        
        Strategy:
        1. First try to use ToolMetadata.side_effect if available (authoritative)
        2. Fall back to heuristic detection from tool name/params
        
        Args:
            tool: Tool name
            params: Tool parameters
        
        Returns:
            List of predicted side-effects
        """
        predicted = []
        
        # Strategy 1: Use ToolMetadata if available (authoritative)
        if self.tool_provider:
            try:
                # Try to get tool spec from provider
                spec = None
                if hasattr(self.tool_provider, 'get_spec'):
                    spec = self.tool_provider.get_spec(tool)
                elif hasattr(self.tool_provider, '_specs') and tool in self.tool_provider._specs:
                    spec = self.tool_provider._specs[tool]
                
                if spec and hasattr(spec, 'tool_metadata') and spec.tool_metadata:
                    metadata = spec.tool_metadata
                    if hasattr(metadata, 'side_effect') and metadata.side_effect:
                        # Map SideEffect enum to specific SideEffectType
                        predicted_type = self._map_side_effect_to_type(metadata.side_effect, tool, params)
                        if predicted_type:
                            predicted.append(PredictedSideEffect(
                                type=predicted_type,
                                target=self._extract_target(predicted_type, params),
                                confidence="high",  # High confidence from metadata
                            ))
                            return predicted  # Authoritative, no need for heuristics
            except Exception:
                # Fall through to heuristic detection
                pass
        
        # Strategy 2: Heuristic detection (fallback)
        # Filesystem side-effects
        fs_read = detect_filesystem_side_effect(tool, params, "read")
        if fs_read:
            predicted.append(PredictedSideEffect(
                type=fs_read,
                target=params.get("path") or params.get("file"),
                confidence="medium",  # Medium confidence from heuristics
            ))
        
        fs_write = detect_filesystem_side_effect(tool, params, "write")
        if fs_write:
            predicted.append(PredictedSideEffect(
                type=fs_write,
                target=params.get("path") or params.get("file"),
                confidence="medium",
            ))
        
        fs_delete = detect_filesystem_side_effect(tool, params, "delete")
        if fs_delete:
            predicted.append(PredictedSideEffect(
                type=fs_delete,
                target=params.get("path") or params.get("file"),
                confidence="medium",
            ))
        
        # Network side-effects
        net_egress = detect_network_side_effect(tool, params, "egress")
        if net_egress:
            predicted.append(PredictedSideEffect(
                type=net_egress,
                target=params.get("url") or params.get("host"),
                confidence="medium",
            ))
        
        # Exec side-effects
        exec_effect = detect_exec_side_effect(tool, params)
        if exec_effect:
            predicted.append(PredictedSideEffect(
                type=exec_effect,
                target=params.get("command") or params.get("cmd"),
                confidence="medium",
            ))
        
        return predicted
    
    def _map_side_effect_to_type(self, side_effect: Any, tool: str, params: dict) -> Optional[SideEffectType]:
        """
        Map SideEffect enum to specific SideEffectType based on context
        
        Args:
            side_effect: SideEffect enum value
            tool: Tool name
            params: Tool parameters
        
        Returns:
            Specific SideEffectType or None
        """
        # Import SideEffect enum
        try:
            from failcore.core.tools.metadata import SideEffect
            
            if not isinstance(side_effect, SideEffect):
                # Try to convert string to enum
                if isinstance(side_effect, str):
                    side_effect = SideEffect(side_effect.lower())
                else:
                    return None
            
            # Map SideEffect to SideEffectType with context-aware refinement
            if side_effect == SideEffect.FS:
                # Infer read/write/delete from tool name or params
                if "write" in tool.lower() or "create" in tool.lower() or params.get("content"):
                    return SideEffectType.FS_WRITE
                elif "delete" in tool.lower() or "remove" in tool.lower():
                    return SideEffectType.FS_DELETE
                else:
                    return SideEffectType.FS_READ  # Default to read
            
            elif side_effect == SideEffect.NETWORK:
                # Default to egress for network
                return SideEffectType.NET_EGRESS
            
            elif side_effect == SideEffect.EXEC:
                # Infer subprocess/command/script from tool name
                if "subprocess" in tool.lower():
                    return SideEffectType.EXEC_SUBPROCESS
                elif "script" in tool.lower():
                    return SideEffectType.EXEC_SCRIPT
                else:
                    return SideEffectType.EXEC_COMMAND
            
            elif side_effect == SideEffect.PROCESS:
                # Infer spawn/kill/signal from tool name or params
                if "spawn" in tool.lower() or "start" in tool.lower():
                    return SideEffectType.PROCESS_SPAWN
                elif "kill" in tool.lower() or "terminate" in tool.lower():
                    return SideEffectType.PROCESS_KILL
                else:
                    return SideEffectType.PROCESS_SIGNAL
            
        except Exception:
            pass
        
        return None
    
    def _extract_target(self, side_effect_type: SideEffectType, params: dict) -> Optional[str]:
        """Extract target from params based on side effect type"""
        from .side_effects import get_category_for_type
        category = get_category_for_type(side_effect_type)
        
        if category == SideEffectCategory.FILESYSTEM:
            return params.get("path") or params.get("file") or params.get("filepath")
        elif category == SideEffectCategory.NETWORK:
            return params.get("url") or params.get("host") or params.get("hostname")
        elif category == SideEffectCategory.EXEC:
            return params.get("command") or params.get("cmd") or params.get("script")
        elif category == SideEffectCategory.PROCESS:
            return str(params.get("pid")) if params.get("pid") else None
        
        return None


__all__ = [
    "SideEffectBoundaryGate",
    "PredictedSideEffect",
]
