# failcore/core/validate/contracts/v1/policy.py
"""
PolicyV1: Validation policy contract (versioned schema).

This is the single source of truth for validation behavior.
All policy sources (YAML, JSON, TOML, UI) must compile into this form.

Design principles:
- Serializable (JSON-compatible)
- Version-controlled
- Append-only fields (no breaking changes)
- Clear enforcement semantics
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    # Fallback for environments without Pydantic
    from dataclasses import dataclass, field as Field
    BaseModel = object  # type: ignore
    ConfigDict = lambda **kwargs: None  # type: ignore


class EnforcementMode(str, Enum):
    """
    Enforcement mode for validation rules.
    
    - SHADOW: Observe only, never block (log decisions)
    - WARN: Log warnings but don't block execution
    - BLOCK: Block execution on rule violation
    """
    SHADOW = "shadow"
    WARN = "warn"
    BLOCK = "block"


class ExceptionV1(BaseModel):
    """
    Time-limited exception to a validation rule.
    
    Allows temporary bypasses with full audit trail.
    """
    model_config = ConfigDict(extra="forbid")
    
    # Required fields
    rule_id: str = Field(description="Rule ID to bypass (e.g., FC_NET_SSRF_INTERNAL)")
    reason: str = Field(description="Human-readable justification")
    expires_at: str = Field(description="ISO8601 expiration timestamp")
    
    # Optional fields
    scope: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Scope restriction (e.g., {'tool': 'http_get', 'param': 'url'})"
    )
    created_by: Optional[str] = Field(default=None, description="Creator identity")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    
    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if exception has expired
        
        Args:
            current_time: Current time to check against (required for core extraction)
                         For core extraction, this must be provided by the caller
                         If None, treats as expired (fail-closed)
        
        Returns:
            True if exception has expired
        """
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
            # For core extraction: current_time must be provided by the caller
            # If None, treat as expired (fail-closed)
            if current_time is None:
                return True
            # Ensure current_time has timezone if expiry has timezone
            if expiry.tzinfo and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=expiry.tzinfo)
            return current_time > expiry
        except Exception:
            return True  # Treat parse errors as expired


class OverrideConfigV1(BaseModel):
    """
    Emergency override (break-glass) configuration.
    
    Allows explicit bypasses with audit trail.
    """
    model_config = ConfigDict(extra="forbid")
    
    enabled: bool = Field(default=False, description="Enable override mechanism")
    require_token: bool = Field(default=True, description="Require override token")
    token_env_var: str = Field(default="FAILCORE_OVERRIDE_TOKEN", description="Environment variable for token")
    expires_at: Optional[str] = Field(default=None, description="Global override expiration")
    audit_required: bool = Field(default=True, description="Require audit logging for overrides")


class ValidatorConfigV1(BaseModel):
    """
    Configuration for a single validator.
    
    Combines:
    - Validator identity (id, domain)
    - Enforcement mode (shadow/warn/block)
    - Rule-specific configuration
    - Exceptions and overrides
    """
    model_config = ConfigDict(extra="allow")  # Allow validator-specific fields
    
    # Required fields
    id: str = Field(description="Validator ID (e.g., 'network_ssrf')")
    enabled: bool = Field(default=True, description="Enable this validator")
    
    # Enforcement
    enforcement: EnforcementMode = Field(
        default=EnforcementMode.BLOCK,
        description="Enforcement mode: shadow/warn/block"
    )
    
    # Optional metadata
    domain: Optional[str] = Field(
        default=None,
        description="Validator domain/pack (e.g., 'security', 'network')"
    )
    priority: int = Field(
        default=100,
        description="Execution priority (lower runs first)"
    )
    
    # Rule configuration (validator-specific)
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Validator-specific configuration"
    )
    
    # Exceptions and overrides
    exceptions: List[ExceptionV1] = Field(
        default_factory=list,
        description="Time-limited exceptions to this validator"
    )
    allow_override: bool = Field(
        default=False,
        description="Allow emergency override for this validator"
    )


class PolicyV1(BaseModel):
    """
    PolicyV1: The canonical validation policy.
    
    This is the single source of truth for validation behavior.
    All policy sources must compile into this form.
    
    Design:
    - version: Policy schema version (for future migrations)
    - builtin: List of validator configurations
    - global_override: Emergency override settings
    - metadata: Policy provenance and audit information
    """
    model_config = ConfigDict(extra="forbid")
    
    # Version
    version: str = Field(default="v1", description="Policy schema version")
    
    # Validators
    validators: Dict[str, ValidatorConfigV1] = Field(
        default_factory=dict,
        description="Validator configurations keyed by validator ID"
    )
    
    # Global override
    global_override: OverrideConfigV1 = Field(
        default_factory=OverrideConfigV1,
        description="Global emergency override configuration"
    )
    
    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Policy metadata (author, created_at, source, etc.)"
    )
    
    def get_validator_config(self, validator_id: str) -> Optional[ValidatorConfigV1]:
        """Get configuration for a specific validator"""
        return self.validators.get(validator_id)
    
    def get_enabled_validators(self) -> List[ValidatorConfigV1]:
        """Get all enabled builtin sorted by priority"""
        enabled = [v for v in self.validators.values() if v.enabled]
        return sorted(enabled, key=lambda v: v.priority)
    
    def get_validators_by_domain(self, domain: str) -> List[ValidatorConfigV1]:
        """Get all builtin in a specific domain"""
        return [v for v in self.validators.values() if v.domain == domain and v.enabled]


__all__ = [
    "EnforcementMode",
    "ExceptionV1",
    "OverrideConfigV1",
    "ValidatorConfigV1",
    "PolicyV1",
]
