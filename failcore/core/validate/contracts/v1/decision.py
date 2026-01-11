# failcore/core/validate/contracts/v1/decision.py
"""
DecisionV1: Stable validation decision contract.

This is the output of all builtin.
It must be:
- Stable (fields are append-only, codes are immutable)
- Explainable (human-readable + machine-readable)
- Auditable (contains all evidence)

Design principles:
- Decision codes are immutable once published (e.g., FC_NET_SSRF_INTERNAL)
- Fields are append-only (new versions add fields, never change meaning)
- All decisions are explainable (message + evidence)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from enum import Enum

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    from dataclasses import dataclass, field as Field
    BaseModel = object  # type: ignore
    ConfigDict = lambda **kwargs: None  # type: ignore


class DecisionOutcome(str, Enum):
    """
    Validation decision outcome.
    
    - ALLOW: Validation passed, execution may proceed
    - WARN: Drift detected, execution proceeds with warning
    - BLOCK: Critical violation, execution blocked
    """
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


class RiskLevel(str, Enum):
    """
    Risk level for validation decisions.
    
    Used for prioritization and reporting.
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DecisionV1(BaseModel):
    """
    Stable validation decision output.
    
    This is the canonical output format for all builtin.
    
    Core fields (stable, required):
    - decision: allow | warn | block
    - code: Stable, referenceable identifier (e.g., FC_NET_SSRF_INTERNAL)
    - message: Human-readable explanation
    - evidence: Structured audit data
    
    Extension fields (stable, optional):
    - risk_level: Critical | high | medium | low | info
    - confidence: Match certainty (0.0-1.0)
    - overrideable: Whether this decision can be overridden
    - requires_approval: Whether this requires human approval
    - tags: Audit and compliance markers
    - remediation: How to fix or relax the policy
    
    Code naming convention: FC_{DOMAIN}_{CATEGORY}_{SPECIFIC}
    Examples:
    - FC_NET_SSRF_INTERNAL
    - FC_NET_SSRF_METADATA
    - FC_FS_PATH_TRAVERSAL
    - FC_FS_SANDBOX_VIOLATION
    - FC_RES_TOKEN_LIMIT
    - FC_RES_COST_LIMIT
    - FC_SEC_EXEC_BLOCKED
    - FC_CONTRACT_TYPE_MISMATCH
    """
    model_config = ConfigDict(extra="allow")  # Allow future extensions
    
    # Core fields (required, stable)
    decision: DecisionOutcome = Field(description="Validation outcome: allow/warn/block")
    code: str = Field(description="Stable decision code (e.g., FC_NET_SSRF_INTERNAL)")
    message: str = Field(description="Human-readable explanation")
    
    # Evidence (required, stable)
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured evidence for audit trail"
    )
    
    # Metadata (required, stable)
    validator_id: str = Field(description="Validator that produced this decision")
    rule_id: Optional[str] = Field(
        default=None,
        description="Specific rule within validator (if applicable)"
    )
    
    # Extension fields (optional, stable)
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM,
        description="Risk level: critical/high/medium/low/info"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Match confidence (0.0-1.0)"
    )
    overrideable: bool = Field(
        default=False,
        description="Whether this decision can be overridden"
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this requires human approval"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for audit and compliance (e.g., ['GDPR', 'PCI-DSS'])"
    )
    remediation: Optional[str] = Field(
        default=None,
        description="How to fix or relax the policy"
    )
    
    # Tool context (optional)
    tool: Optional[str] = Field(default=None, description="Tool name")
    step_id: Optional[str] = Field(default=None, description="Step identifier")
    
    @property
    def is_blocking(self) -> bool:
        """Whether this decision blocks execution"""
        return self.decision == DecisionOutcome.BLOCK
    
    @property
    def is_warning(self) -> bool:
        """Whether this decision is a warning"""
        return self.decision == DecisionOutcome.WARN
    
    @property
    def is_allow(self) -> bool:
        """Whether this decision allows execution"""
        return self.decision == DecisionOutcome.ALLOW
    
    @classmethod
    def allow(
        cls,
        code: str,
        validator_id: str,
        message: str = "Validation passed",
        **kwargs
    ) -> DecisionV1:
        """Create an ALLOW decision"""
        return cls(
            decision=DecisionOutcome.ALLOW,
            code=code,
            validator_id=validator_id,
            message=message,
            **kwargs
        )
    
    @classmethod
    def warn(
        cls,
        code: str,
        validator_id: str,
        message: str,
        evidence: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> DecisionV1:
        """Create a WARN decision"""
        return cls(
            decision=DecisionOutcome.WARN,
            code=code,
            validator_id=validator_id,
            message=message,
            evidence=evidence or {},
            **kwargs
        )
    
    @classmethod
    def block(
        cls,
        code: str,
        validator_id: str,
        message: str,
        evidence: Optional[Dict[str, Any]] = None,
        risk_level: RiskLevel = RiskLevel.HIGH,
        **kwargs
    ) -> DecisionV1:
        """Create a BLOCK decision"""
        return cls(
            decision=DecisionOutcome.BLOCK,
            code=code,
            validator_id=validator_id,
            message=message,
            evidence=evidence or {},
            risk_level=risk_level,
            **kwargs
        )


__all__ = [
    "DecisionOutcome",
    "RiskLevel",
    "DecisionV1",
]
