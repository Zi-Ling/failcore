"""
Egress Event - Post-execution event model

Written AFTER execution completes to capture:
- What actually happened
- Observed target (actual network/fs/exec)
- Evidence from enrichers

Design:
- Single event per execution
- Includes both observed data and enricher evidence
- Structurally similar to AttemptEvent for homogeneity

This event exists in both preflight and egress gate modes.
"""

from __future__ import annotations

from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..rules.schemas import EvidenceSchema, TargetSchema


@dataclass
class EgressEvent:
    """
    Egress event - post-execution record
    
    Written AFTER execution completes.
    Captures actual execution results and enricher evidence.
    
    Architecture constraint:
    - Must reference attempt_id for correlation
    - Contains ONLY evidence, NEVER verdict (verdict is in AttemptEvent)
    - Enrichers add evidence to this event
    
    Field structure matches AttemptEvent for homogeneous trace.
    """
    # Identity (correlates with AttemptEvent)
    attempt_id: str
    run_id: str
    step_id: Optional[str] = None
    
    # Timing
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: Optional[float] = None
    
    # Tool context (same as attempt)
    tool: str = ""
    params: Optional[Dict[str, Any]] = None
    
    # Execution result
    result: Optional[Any] = None
    error: Optional[str] = None
    status: str = "ok"  # "ok", "error", "blocked"
    
    # Target (observed from actual execution)
    target: Optional[TargetSchema] = None
    
    # Evidence (added by enrichers - NEVER by gates)
    evidence: List[EvidenceSchema] = field(default_factory=list)
    
    # Raw evidence dict (legacy compatibility)
    evidence_raw: Optional[Dict[str, Any]] = None
    
    # Metadata
    context: Optional[Dict[str, Any]] = None
    
    def add_evidence(self, evidence: EvidenceSchema) -> None:
        """Add evidence (enricher use only)"""
        self.evidence.append(evidence)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        data = {
            "attempt_id": self.attempt_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "ts": self.ts,
            "tool": self.tool,
            "status": self.status,
        }
        
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        
        if self.params:
            data["params"] = self.params
        
        if self.result:
            data["result"] = self.result
        
        if self.error:
            data["error"] = self.error
        
        if self.target:
            data["target"] = {
                "type": self.target.type.value if hasattr(self.target.type, 'value') else self.target.type,
                "observed": self.target.observed,
                "observed_confidence": self.target.observed_confidence,
                "inferred": self.target.inferred,
            }
        
        if self.evidence:
            data["evidence"] = [
                {
                    "category": e.category,
                    "findings": e.findings,
                    "confidence": e.confidence,
                    "enricher": e.enricher_name,
                }
                for e in self.evidence
            ]
        
        if self.evidence_raw:
            data["evidence_raw"] = self.evidence_raw
        
        if self.context:
            data["context"] = self.context
        
        return data


__all__ = ["EgressEvent"]
