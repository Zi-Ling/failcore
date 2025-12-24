# failcore/core/tools/metadata.py
"""
Tool metadata definitions and validation.

This module defines security-relevant metadata for tools and enforces
non-negotiable safety invariants at registration and execution time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SideEffect(str, Enum):
    READ = "read"
    WRITE = "write"
    EXEC = "exec"
    NETWORK = "network"


class DefaultPolicy(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class ToolMetadata:
    """
    Immutable tool metadata used for security and policy enforcement.
    """

    risk_level: RiskLevel
    side_effect: SideEffect
    default_policy: DefaultPolicy

    @property
    def requires_strict_mode(self) -> bool:
        """
        Whether this tool requires strict validation to be enabled.
        """
        return self.risk_level == RiskLevel.HIGH

    def validate_static_invariants(self) -> None:
        """
        Validate invariants that must always hold, regardless of runtime config.
        """
        if self.risk_level == RiskLevel.HIGH and self.default_policy == DefaultPolicy.ALLOW:
            raise ValueError(
                "HIGH risk tools cannot have default_policy=ALLOW. "
                "Use WARN or BLOCK."
            )


def validate_metadata_runtime(
    metadata: ToolMetadata,
    strict_enabled: bool,
) -> None:
    """
    Validate metadata against runtime configuration.

    Args:
        metadata: ToolMetadata instance
        strict_enabled: Whether strict validation is enabled for this tool

    Raises:
        ValueError if runtime configuration violates metadata requirements
    """
    metadata.validate_static_invariants()

    if metadata.requires_strict_mode and not strict_enabled:
        raise ValueError(
            "HIGH risk tools require strict validation mode to be enabled."
        )


DEFAULT_METADATA_PROFILES: Dict[str, ToolMetadata] = {
    "read_file": ToolMetadata(
        risk_level=RiskLevel.MEDIUM,
        side_effect=SideEffect.READ,
        default_policy=DefaultPolicy.ALLOW,
    ),
    "write_file": ToolMetadata(
        risk_level=RiskLevel.HIGH,
        side_effect=SideEffect.WRITE,
        default_policy=DefaultPolicy.BLOCK,
    ),
    "http_request": ToolMetadata(
        risk_level=RiskLevel.HIGH,
        side_effect=SideEffect.NETWORK,
        default_policy=DefaultPolicy.BLOCK,
    ),
    "python_exec": ToolMetadata(
        risk_level=RiskLevel.HIGH,
        side_effect=SideEffect.EXEC,
        default_policy=DefaultPolicy.BLOCK,
    ),
    "delete_file": ToolMetadata(
        risk_level=RiskLevel.HIGH,
        side_effect=SideEffect.WRITE,
        default_policy=DefaultPolicy.BLOCK,
    ),
    "list_dir": ToolMetadata(
        risk_level=RiskLevel.LOW,
        side_effect=SideEffect.READ,
        default_policy=DefaultPolicy.ALLOW,
    ),
    "string_transform": ToolMetadata(
        risk_level=RiskLevel.LOW,
        side_effect=SideEffect.READ,
        default_policy=DefaultPolicy.ALLOW,
    ),
}
