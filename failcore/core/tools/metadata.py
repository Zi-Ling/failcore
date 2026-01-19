# failcore/core/tools/metadata.py
"""
Tool metadata definitions and validation.

This module defines security-relevant metadata for tools and enforces
non-negotiable safety invariants at registration and execution time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SideEffect(str, Enum):
    FS = "FS"             # File system boundary (read/write enforced by policy)
    NETWORK = "NETWORK"   # Network I/O boundary
    EXEC = "EXEC"         # Local execution (shell, subprocess, binaries)
    PROCESS = "PROCESS"   # Process lifecycle control (spawn, kill, signals)


class DefaultAction(str, Enum):
    """
    Tool-level fallback action.

    Applies ONLY when no active policy/validator makes a decision.
    This action NEVER overrides run-level policy or strict mode.
    """
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"


class Determinism(str, Enum):
    """
    Tool determinism classification.
    
    Used by optimizer to determine caching safety:
    - DETERMINISTIC: Same inputs -> same outputs (safe to cache)
    - NON_DETERMINISTIC: Outputs vary (e.g., get_time, random)
    - UNKNOWN: Not specified (use conservative confidence)
    """
    DETERMINISTIC = "DETERMINISTIC"
    NON_DETERMINISTIC = "NON_DETERMINISTIC"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ToolMetadata:
    """
    Immutable tool metadata used for security and policy enforcement.

    - risk_level defaults to MEDIUM
    - default_action defaults to WARN
    - side_effect is Optional: None means "unspecified/unknown" (not "safe")
    - determinism: DETERMINISTIC/NON_DETERMINISTIC/UNKNOWN (default: UNKNOWN)
    """
    side_effect: Optional[SideEffect] = None
    risk_level: RiskLevel = RiskLevel.MEDIUM
    default_action: DefaultAction = DefaultAction.WARN
    determinism: Determinism = Determinism.UNKNOWN

    @property
    def requires_strict_mode(self) -> bool:
        """
        Strict is required only for high-risk local execution tools.
        """
        return (self.risk_level == RiskLevel.HIGH) and (self.side_effect == SideEffect.EXEC)

    def validate_static_invariants(self) -> None:
        """
        Validate invariants that must always hold, regardless of runtime config.
        """
        # Never allow permissive fallback for high-risk tools.
        if self.risk_level == RiskLevel.HIGH and self.default_action == DefaultAction.ALLOW:
            raise ValueError(
                "HIGH risk tools cannot have default_action=ALLOW. Use WARN or BLOCK."
            )

        # Local execution is always sensitive; never allow permissive fallback.
        if self.side_effect == SideEffect.EXEC and self.default_action == DefaultAction.ALLOW:
            raise ValueError(
                "EXEC tools cannot have default_action=ALLOW. Use WARN or BLOCK."
            )


def validate_metadata_runtime(metadata: ToolMetadata, strict_enabled: bool) -> None:
    """
    Validate metadata against runtime configuration.
    """
    metadata.validate_static_invariants()

    if metadata.requires_strict_mode and not strict_enabled:
        raise ValueError(
            "High-risk EXEC tools require strict validation mode to be enabled."
        )


DEFAULT_METADATA_PROFILES: Dict[str, ToolMetadata] = {
    "read_file": ToolMetadata(
        side_effect=SideEffect.FS,
        risk_level=RiskLevel.MEDIUM,
        default_action=DefaultAction.WARN,
        determinism=Determinism.DETERMINISTIC,  # Same file -> same content (at snapshot)
    ),
    "write_file": ToolMetadata(
        side_effect=SideEffect.FS,
        risk_level=RiskLevel.MEDIUM,
        default_action=DefaultAction.WARN,
        determinism=Determinism.DETERMINISTIC,  # Same params -> same effect
    ),
    "delete_file": ToolMetadata(
        side_effect=SideEffect.FS,
        risk_level=RiskLevel.HIGH,
        default_action=DefaultAction.BLOCK,
        determinism=Determinism.DETERMINISTIC,  # Same params -> same effect
    ),
    "list_dir": ToolMetadata(
        side_effect=SideEffect.FS,
        risk_level=RiskLevel.LOW,
        default_action=DefaultAction.WARN,
        determinism=Determinism.DETERMINISTIC,  # Same dir -> same listing (at snapshot)
    ),
    "http_request": ToolMetadata(
        side_effect=SideEffect.NETWORK,
        risk_level=RiskLevel.HIGH,
        default_action=DefaultAction.BLOCK,
        determinism=Determinism.NON_DETERMINISTIC,  # External API may return different results
    ),
    "python_exec": ToolMetadata(
        side_effect=SideEffect.EXEC,
        risk_level=RiskLevel.HIGH,
        default_action=DefaultAction.BLOCK,
        determinism=Determinism.UNKNOWN,  # Depends on code being executed
    ),
    "shell_exec": ToolMetadata(
        side_effect=SideEffect.EXEC,
        risk_level=RiskLevel.HIGH,
        default_action=DefaultAction.BLOCK,
        determinism=Determinism.UNKNOWN,  # Depends on command
    ),
}
