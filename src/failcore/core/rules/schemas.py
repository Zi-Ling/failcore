"""
Unified Schemas - Canonical field definitions

Defines schema structures shared across gates and enrichers to ensure
event model consistency between preflight and egress boundaries.

Design principles:
1. Target has inferred (from params) and observed (from execution) variants
2. Verdict is written only by gates (preflight or egress)
3. Evidence is written only by enrichers (post-execution)
4. Schema enforces semantic constraints on field usage
"""

from __future__ import annotations

from typing import Optional, Literal
from dataclasses import dataclass
from enum import Enum


class TargetType(str, Enum):
    """Target type classification"""
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    EXECUTION = "execution"
    DATABASE = "database"
    UNKNOWN = "unknown"


@dataclass
class TargetSchema:
    """
    Unified target schema for side-effects
    
    Architecture principle:
    - inferred: derived from tool parameters (pre-execution, available in gates)
    - observed: captured from actual execution (post-execution, available in enrichers)
    - Decision priority: observed > inferred (when both available)
    
    Usage:
    - Gates use inferred target for preflight decisions
    - Enrichers add observed target for evidence
    - Audit/replay use observed when available, fallback to inferred
    """
    type: TargetType
    
    # Pre-execution (available in gates)
    inferred: Optional[str] = None
    inferred_confidence: Literal["high", "medium", "low"] = "medium"
    
    # Post-execution (available in enrichers)
    observed: Optional[str] = None
    observed_confidence: Literal["high", "medium", "low"] = "high"
    
    # Metadata
    details: Optional[dict] = None
    
    def get_authoritative(self) -> Optional[str]:
        """Get authoritative target (observed > inferred)"""
        return self.observed or self.inferred


class VerdictAction(str, Enum):
    """Verdict actions (written only by gates)"""
    ALLOW = "allow"
    BLOCK = "block"
    SANITIZE = "sanitize"
    WARN = "warn"
    WARN_APPROVAL_NEEDED = "warn_approval_needed"  # Downgraded from REQUIRE_APPROVAL


@dataclass
class VerdictSchema:
    """
    Unified verdict schema
    
    Architecture constraint:
    - ONLY gates can write verdicts (preflight gate or egress gate)
    - Enrichers NEVER write verdicts (only evidence)
    
    Usage:
    - Preflight gate: writes verdict before tool execution
    - Egress gate: writes verdict before response forwarding
    - Verdict is authoritative decision point
    """
    action: VerdictAction
    reason: str
    rule_name: Optional[str] = None
    rule_category: Optional[str] = None
    confidence: float = 1.0
    gate_type: Literal["preflight", "egress"] = "preflight"
    
    # Context
    triggered_by: Optional[str] = None  # DLP pattern, semantic rule, policy, etc.
    metadata: Optional[dict] = None


@dataclass
class EvidenceSchema:
    """
    Unified evidence schema
    
    Architecture constraint:
    - ONLY enrichers can write evidence (post-execution)
    - Gates NEVER write evidence (only verdicts)
    
    Usage:
    - Enrichers scan completed events and add evidence
    - Evidence is supplementary information for audit
    - Evidence does NOT influence gates (gates already decided)
    """
    category: Literal["dlp", "taint", "semantic", "effects", "usage"]
    findings: dict
    confidence: float = 1.0
    
    # Metadata
    enricher_name: str = ""
    enricher_version: str = "0.1.0"
    metadata: Optional[dict] = None


__all__ = [
    "TargetType",
    "TargetSchema",
    "VerdictAction",
    "VerdictSchema",
    "EvidenceSchema",
]
