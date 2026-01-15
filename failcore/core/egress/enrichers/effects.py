"""
Effects Enricher - Side-effect annotation

Annotates egress events with side-effect information for audit trail.
Records side-effect types, targets, and boundary crossing data.

Outputs:
- event.evidence["side_effect_type"]: detected side-effect type
- event.evidence["side_effect_target"]: target (path/host/command)
- event.evidence["side_effect_category"]: side-effect category
- event.evidence["boundary_crossed"]: bool (if boundary was crossed)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types import EgressEvent
from ...guards.effects.side_effects import SideEffectType, SideEffectCategory
from ...guards.effects.detection import (
    detect_filesystem_side_effect,
    detect_network_side_effect,
    detect_exec_side_effect,
)


class EffectsEnricher:
    """
    Side-effects enricher for egress events
    
    Responsibilities:
    - Detect side-effect type from tool/params
    - Annotate side-effect metadata to evidence
    - Record boundary crossing information
    - Never block traffic (post-execution analysis)
    
    Design:
    - Uses guards/effects detection logic
    - Heuristic-based detection
    - Comprehensive audit trail
    """
    
    def __init__(self):
        """Initialize effects enricher"""
        pass
    
    def enrich(self, event: EgressEvent) -> None:
        """
        Enrich event with side-effect information
        
        Args:
            event: Egress event to enrich
        """
        evidence = getattr(event, "evidence", None)
        if evidence is None:
            evidence = {}
            event.evidence = evidence  # type: ignore[assignment]
        if not isinstance(evidence, dict):
            return
        
        # Extract tool and params from evidence
        tool_name = evidence.get("tool", "")
        params = evidence.get("params", {})
        
        if not tool_name:
            # No tool info, skip side-effect detection
            evidence["side_effect_type"] = "unknown"
            return
        
        # Detect side-effects
        try:
            side_effect_type = self._detect_side_effect(tool_name, params)
            
            if side_effect_type:
                evidence["side_effect_type"] = side_effect_type.value
                evidence["side_effect_category"] = self._get_category(side_effect_type).value
                
                # Extract target
                target = self._extract_target(tool_name, params, side_effect_type)
                if target:
                    evidence["side_effect_target"] = target
                
                # Check if boundary might have been crossed
                # (We can't know for sure post-execution, but can infer)
                evidence["boundary_check_recommended"] = self._should_check_boundary(side_effect_type)
            else:
                # No side-effect detected
                evidence["side_effect_type"] = "none"
                evidence["side_effect_category"] = "none"
        
        except Exception as e:
            # Defensive: never crash pipeline
            evidence["side_effect_type"] = "error"
            evidence["side_effect_error"] = str(e)
    
    def _detect_side_effect(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Optional[SideEffectType]:
        """
        Detect side-effect type from tool and params
        
        Args:
            tool_name: Tool name
            params: Tool parameters
        
        Returns:
            Side-effect type if detected
        """
        # Try filesystem detection
        for operation in ["read", "write", "delete"]:
            se_type = detect_filesystem_side_effect(tool_name, params, operation)
            if se_type:
                return se_type
        
        # Try network detection
        for direction in ["egress", "ingress", "private"]:
            se_type = detect_network_side_effect(tool_name, params, direction)
            if se_type:
                return se_type
        
        # Try exec detection
        se_type = detect_exec_side_effect(tool_name, params)
        if se_type:
            return se_type
        
        return None
    
    def _get_category(self, side_effect_type: SideEffectType) -> SideEffectCategory:
        """
        Get category for side-effect type
        
        Args:
            side_effect_type: Side-effect type
        
        Returns:
            Side-effect category
        """
        # Map types to categories
        if side_effect_type in (
            SideEffectType.FS_READ,
            SideEffectType.FS_WRITE,
            SideEffectType.FS_DELETE,
        ):
            return SideEffectCategory.FILESYSTEM
        
        elif side_effect_type in (
            SideEffectType.NET_EGRESS,
            SideEffectType.NET_INGRESS,
            SideEffectType.NET_PRIVATE,
        ):
            return SideEffectCategory.NETWORK
        
        elif side_effect_type in (
            SideEffectType.EXEC_COMMAND,
            SideEffectType.EXEC_SUBPROCESS,
            SideEffectType.EXEC_SCRIPT,
        ):
            return SideEffectCategory.EXEC
        
        else:
            return None
    
    def _extract_target(
        self,
        tool_name: str,
        params: Dict[str, Any],
        side_effect_type: SideEffectType,
    ) -> Optional[str]:
        """
        Extract side-effect target from params
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            side_effect_type: Side-effect type
        
        Returns:
            Target string if found
        """
        category = self._get_category(side_effect_type)
        
        if category == SideEffectCategory.FILESYSTEM:
            # Look for path/file parameter
            return (
                params.get("path") or
                params.get("file") or
                params.get("filepath") or
                params.get("directory")
            )
        
        elif category == SideEffectCategory.NETWORK:
            # Look for URL/host parameter
            return (
                params.get("url") or
                params.get("host") or
                params.get("hostname") or
                params.get("endpoint")
            )
        
        elif category == SideEffectCategory.EXEC:
            # Look for command parameter
            return (
                params.get("command") or
                params.get("cmd") or
                params.get("script")
            )
        
        return None
    
    def _should_check_boundary(self, side_effect_type: SideEffectType) -> bool:
        """
        Check if boundary verification is recommended
        
        Args:
            side_effect_type: Side-effect type
        
        Returns:
            True if boundary check recommended
        """
        # Recommend boundary check for all side-effects
        # (write/delete/egress are higher priority)
        return side_effect_type in (
            SideEffectType.FS_WRITE,
            SideEffectType.FS_DELETE,
            SideEffectType.NET_EGRESS,
            SideEffectType.EXEC_COMMAND,
            SideEffectType.EXEC_SUBPROCESS,
            SideEffectType.EXEC_SCRIPT,
        )


__all__ = ["EffectsEnricher"]
