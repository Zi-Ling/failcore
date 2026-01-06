# failcore/core/errors/side_effect.py
"""
Side-Effect Boundary Crossing Errors

Converts SideEffectBoundaryCrossed into standard FailCore errors.
Crossing = direct failure (no severity grading, no soft warnings).
"""

from typing import Optional, Dict, Any

from . import codes
from .exceptions import FailCoreError

from ..audit.side_effect_auditor import CrossingRecord
from ..audit.side_effects import SideEffectType


class SideEffectBoundaryCrossedError(FailCoreError):
    """
    Side-effect boundary crossing error
    
    Raised when a side-effect crosses the declared boundary.
    This is a direct failure - no warnings, no soft blocks.
    Crossing = failure.
    """
    
    def __init__(
        self,
        crossing_record: CrossingRecord,
        message: Optional[str] = None,
    ):
        """
        Initialize side-effect boundary crossing error
        
        Args:
            crossing_record: Crossing record containing crossing details
            message: Optional error message (auto-generated if None)
        """
        if message is None:
            message = self._generate_message(crossing_record)
        
        error_code = self._get_error_code(crossing_record.crossing_type)
        
        super().__init__(
            message=message,
            error_code=error_code,
            error_type="SIDE_EFFECT_BOUNDARY_CROSSED",
            details={
                "crossing_type": crossing_record.crossing_type.value if isinstance(crossing_record.crossing_type, SideEffectType) else str(crossing_record.crossing_type),
                "observed_category": crossing_record.observed_category,
                "target": crossing_record.target,
                "tool": crossing_record.tool,
                "step_id": crossing_record.step_id,
                "step_seq": crossing_record.step_seq,
                "allowed_categories": crossing_record.allowed_categories,
            },
        )
        self.crossing_record = crossing_record
    
    def _generate_message(self, crossing_record: CrossingRecord) -> str:
        """
        Generate error message from crossing record
        
        Args:
            crossing_record: Crossing record
        
        Returns:
            Error message string
        """
        crossing_type = crossing_record.crossing_type.value if isinstance(crossing_record.crossing_type, SideEffectType) else str(crossing_record.crossing_type)
        target_str = f" (target: {crossing_record.target})" if crossing_record.target else ""
        tool_str = f" by tool '{crossing_record.tool}'" if crossing_record.tool else ""
        allowed_str = ", ".join(crossing_record.allowed_categories) if crossing_record.allowed_categories else "none"
        
        return (
            f"Side-effect boundary crossed: {crossing_type}{target_str}{tool_str}. "
            f"Allowed categories: {allowed_str}"
        )
    
    def _get_error_code(self, crossing_type: SideEffectType) -> str:
        """
        Get error code for crossing type
        
        Args:
            crossing_type: Side-effect type that crossed boundary
        
        Returns:
            Error code string
        """
        if isinstance(crossing_type, SideEffectType):
            type_str = crossing_type.value
        else:
            type_str = str(crossing_type)
        
        # Map side-effect types to error codes
        if type_str.startswith("filesystem."):
            if "write" in type_str:
                return codes.PERMISSION_DENIED  # Filesystem write = permission denied
            elif "delete" in type_str:
                return codes.PERMISSION_DENIED
            else:
                return codes.POLICY_DENIED
        elif type_str.startswith("network."):
            if "private" in type_str:
                return codes.PRIVATE_NETWORK_BLOCKED
            else:
                return codes.POLICY_DENIED
        elif type_str.startswith("exec.") or type_str.startswith("process."):
            return codes.POLICY_DENIED
        else:
            return codes.POLICY_DENIED


__all__ = [
    "SideEffectBoundaryCrossedError",
]
