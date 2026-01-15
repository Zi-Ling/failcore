# failcore/config/validator.py
"""
Configuration Validator

Validates configuration for illegal/misleading combinations.
Returns structured issues with level (warn/error), path, message, hint.
"""

from typing import List, Literal
from dataclasses import dataclass
from .modules import (
    DLPConfig,
    SemanticConfig,
    EffectsConfig,
    TaintConfig,
    DriftConfig,
)


@dataclass(frozen=True)
class ConfigIssue:
    """
    Configuration validation issue
    
    Structured output for CLI/UI/logging.
    """
    level: Literal["warn", "error"]
    path: str  # e.g., "modules.dlp.mode"
    message: str
    hint: str = ""  # Optional hint for fixing
    
    def __str__(self) -> str:
        level_icon = "⚠️" if self.level == "warn" else "❌"
        hint_str = f"\n   Hint: {self.hint}" if self.hint else ""
        return f"{level_icon} [{self.path}] {self.message}{hint_str}"


def validate_config(
    dlp: DLPConfig,
    semantic: SemanticConfig,
    effects: EffectsConfig,
    taint: TaintConfig,
    drift: DriftConfig,
) -> List[ConfigIssue]:
    """
    Validate configuration for illegal/misleading combinations.
    
    Returns:
        List of issues (warn/error level)
    """
    issues = []
    
    # DLP: enabled=false but mode=block (warning)
    if not dlp.enabled and dlp.mode == "block":
        issues.append(ConfigIssue(
            level="warn",
            path="modules.dlp.mode",
            message="mode='block' has no effect when enabled=false (module not registered)",
            hint="Set modules.dlp.enabled=true to enable DLP blocking",
        ))
    
    # DLP: enabled=false but redact=true (warning)
    if not dlp.enabled and dlp.redact:
        issues.append(ConfigIssue(
            level="warn",
            path="modules.dlp.redact",
            message="redact=true has no effect when enabled=false (module not registered)",
            hint="Set modules.dlp.enabled=true to enable DLP redaction",
        ))
    
    # Semantic: enabled=false but min_severity set (warning)
    if not semantic.enabled:
        issues.append(ConfigIssue(
            level="warn",
            path="modules.semantic.min_severity",
            message=f"min_severity={semantic.min_severity.value} has no effect when enabled=false",
            hint="Set modules.semantic.enabled=true to enable semantic guard",
        ))
    
    # Semantic: enabled=false but enabled_categories set (warning)
    if not semantic.enabled and semantic.enabled_categories is not None:
        issues.append(ConfigIssue(
            level="warn",
            path="modules.semantic.enabled_categories",
            message="enabled_categories has no effect when enabled=false",
            hint="Set modules.semantic.enabled=true to enable category filtering",
        ))
    
    # Effects: enabled=false but boundary_preset set (warning)
    if not effects.enabled and effects.boundary_preset != "none":
        issues.append(ConfigIssue(
            level="warn",
            path="modules.effects.boundary_preset",
            message=f"boundary_preset='{effects.boundary_preset}' has no effect when enabled=false",
            hint="Set modules.effects.enabled=true to enable boundary enforcement",
        ))
    
    # Effects: enabled=false but enforce_boundary=true (warning)
    if not effects.enabled and effects.enforce_boundary:
        issues.append(ConfigIssue(
            level="warn",
            path="modules.effects.enforce_boundary",
            message="enforce_boundary=true has no effect when enabled=false",
            hint="Set modules.effects.enabled=true to enable boundary enforcement",
        ))
    
    # Taint: enabled=false but propagation_mode set (warning)
    if not taint.enabled and taint.propagation_mode != "whole":
        issues.append(ConfigIssue(
            level="warn",
            path="modules.taint.propagation_mode",
            message=f"propagation_mode='{taint.propagation_mode}' has no effect when enabled=false",
            hint="Set modules.taint.enabled=true to enable taint tracking",
        ))
    
    # Drift: enabled=false but analysis_only set (warning)
    if not drift.enabled and not drift.analysis_only:
        issues.append(ConfigIssue(
            level="warn",
            path="modules.drift.analysis_only",
            message="analysis_only=false has no effect when enabled=false",
            hint="Set modules.drift.enabled=true to enable drift detection",
        ))
    
    # Effects: boundary_preset='none' but enforce_boundary=true (warning)
    if effects.enabled and effects.boundary_preset == "none" and effects.enforce_boundary:
        issues.append(ConfigIssue(
            level="warn",
            path="modules.effects.enforce_boundary",
            message="enforce_boundary=true with boundary_preset='none' - no boundaries will be enforced",
            hint="Set boundary_preset to 'strict', 'permissive', etc. to enforce boundaries",
        ))
    
    # Drift: enabled but NOT analysis_only (warning - dangerous)
    if drift.enabled and not drift.analysis_only:
        issues.append(ConfigIssue(
            level="warn",
            path="modules.drift.analysis_only",
            message="analysis_only=false - drift detection can BLOCK execution (use with caution)",
            hint="Set analysis_only=true for read-only analysis, or ensure drift rules are well-tuned",
        ))
    
    # Value domain validation (errors)
    if dlp.mode not in ["block", "sanitize", "warn"]:
        issues.append(ConfigIssue(
            level="error",
            path="modules.dlp.mode",
            message=f"Invalid mode value: '{dlp.mode}' (must be 'block', 'sanitize', or 'warn')",
            hint="Set modules.dlp.mode to one of: block, sanitize, warn",
        ))
    
    if taint.propagation_mode not in ["whole", "paths"]:
        issues.append(ConfigIssue(
            level="error",
            path="modules.taint.propagation_mode",
            message=f"Invalid propagation_mode: '{taint.propagation_mode}' (must be 'whole' or 'paths')",
            hint="Set modules.taint.propagation_mode to 'whole' or 'paths'",
        ))
    
    if effects.boundary_preset not in ["strict", "permissive", "read_only", "network_only", "none"]:
        issues.append(ConfigIssue(
            level="error",
            path="modules.effects.boundary_preset",
            message=f"Invalid boundary_preset: '{effects.boundary_preset}'",
            hint="Set modules.effects.boundary_preset to: strict, permissive, read_only, network_only, or none",
        ))
    
    return issues


# Backward compatibility alias
ConfigWarning = ConfigIssue


__all__ = [
    "ConfigIssue",
    "ConfigWarning",  # Alias for backward compatibility
    "validate_config",
]
