"""
DLP Policies

Defines DLP policy actions and decision matrix
"""

from __future__ import annotations

from typing import Dict, Optional
from enum import Enum
from dataclasses import dataclass

from ..taint.tag import DataSensitivity


class DLPAction(str, Enum):
    """DLP policy actions"""
    ALLOW = "allow"
    WARN = "warn"
    SANITIZE = "sanitize"
    BLOCK = "block"
    WARN_APPROVAL_NEEDED = "warn_approval_needed"  # Downgraded from REQUIRE_APPROVAL


@dataclass
class DLPPolicy:
    """
    DLP policy configuration
    
    Attributes:
        action: Policy action
        reason: Policy reason/description
        auto_sanitize: Enable automatic sanitization
        notify: Send notification on trigger
    """
    action: DLPAction
    reason: str = ""
    auto_sanitize: bool = False
    notify: bool = True


class PolicyMatrix:
    """
    DLP policy decision matrix
    
    Maps data sensitivity levels to policy actions
    """
    
    # Default strict policy matrix
    STRICT_MATRIX: Dict[DataSensitivity, DLPPolicy] = {
        DataSensitivity.PUBLIC: DLPPolicy(
            action=DLPAction.ALLOW,
            reason="Public data - no restrictions"
        ),
        DataSensitivity.INTERNAL: DLPPolicy(
            action=DLPAction.WARN,
            reason="Internal data - monitor only"
        ),
        DataSensitivity.CONFIDENTIAL: DLPPolicy(
            action=DLPAction.SANITIZE,
            reason="Confidential data - requires sanitization",
            auto_sanitize=True
        ),
        DataSensitivity.PII: DLPPolicy(
            action=DLPAction.BLOCK,
            reason="PII detected - blocked by policy"
        ),
        DataSensitivity.SECRET: DLPPolicy(
            action=DLPAction.BLOCK,
            reason="Secret/credential detected - blocked by policy"
        ),
    }
    
    # Note: REQUIRE_APPROVAL has been removed and replaced with WARN_APPROVAL_NEEDED
    # This is because REQUIRE_APPROVAL requires control plane infrastructure
    # (state storage, timeout handling, approval injection) which is not yet implemented.
    
    # Permissive policy matrix
    PERMISSIVE_MATRIX: Dict[DataSensitivity, DLPPolicy] = {
        DataSensitivity.PUBLIC: DLPPolicy(
            action=DLPAction.ALLOW,
            reason="Public data - no restrictions"
        ),
        DataSensitivity.INTERNAL: DLPPolicy(
            action=DLPAction.ALLOW,
            reason="Internal data - allowed"
        ),
        DataSensitivity.CONFIDENTIAL: DLPPolicy(
            action=DLPAction.WARN,
            reason="Confidential data - warning only"
        ),
        DataSensitivity.PII: DLPPolicy(
            action=DLPAction.SANITIZE,
            reason="PII detected - auto-sanitize",
            auto_sanitize=True
        ),
        DataSensitivity.SECRET: DLPPolicy(
            action=DLPAction.BLOCK,
            reason="Secret/credential detected - blocked"
        ),
    }
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize policy matrix
        
        Args:
            strict_mode: Use strict policy matrix
        """
        self.strict_mode = strict_mode
        self._matrix = self.STRICT_MATRIX if strict_mode else self.PERMISSIVE_MATRIX
        self._overrides: Dict[DataSensitivity, DLPPolicy] = {}
    
    def get_policy(self, sensitivity: DataSensitivity) -> DLPPolicy:
        """
        Get policy for sensitivity level
        
        Args:
            sensitivity: Data sensitivity level
        
        Returns:
            DLP policy for this sensitivity
        """
        # Check for override first
        if sensitivity in self._overrides:
            return self._overrides[sensitivity]
        
        # Fall back to matrix
        return self._matrix.get(sensitivity, DLPPolicy(
            action=DLPAction.BLOCK,
            reason="Unknown sensitivity - blocked by default"
        ))
    
    def override_policy(self, sensitivity: DataSensitivity, policy: DLPPolicy) -> None:
        """
        Override policy for specific sensitivity level
        
        Args:
            sensitivity: Data sensitivity level
            policy: New policy
        """
        self._overrides[sensitivity] = policy
    
    def reset_overrides(self) -> None:
        """Reset all policy overrides"""
        self._overrides.clear()
    
    def should_block(self, sensitivity: DataSensitivity) -> bool:
        """
        Check if sensitivity level should be blocked
        
        Args:
            sensitivity: Data sensitivity level
        
        Returns:
            True if should block
        """
        policy = self.get_policy(sensitivity)
        return policy.action in (DLPAction.BLOCK, DLPAction.REQUIRE_APPROVAL)
    
    def should_sanitize(self, sensitivity: DataSensitivity) -> bool:
        """
        Check if sensitivity level requires sanitization
        
        Args:
            sensitivity: Data sensitivity level
        
        Returns:
            True if should sanitize
        """
        policy = self.get_policy(sensitivity)
        return policy.action == DLPAction.SANITIZE or policy.auto_sanitize


__all__ = [
    "DLPAction",
    "DLPPolicy",
    "PolicyMatrix",
]
