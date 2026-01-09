# failcore/core/egress/types.py
"""
Egress Event Types - Unified execution egress model

All real-world side effects are normalized into EgressEvent.
This is the single source of truth for execution decisions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EgressType(str, Enum):
    """Egress types following Proxy architecture"""
    NETWORK = "NETWORK"
    FS = "FS"
    EXEC = "EXEC"
    COST = "COST"


class PolicyDecision(str, Enum):
    """Policy decision outcomes"""
    ALLOW = "ALLOW"
    DENY = "DENY"
    WARN = "WARN"


class RiskLevel(str, Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EgressEvent:
    """
    Unified egress event model
    
    Represents a single execution egress (network/fs/exec/cost).
    All downstream systems (trace/audit/cost/dlp) consume this.
    
    Design principles:
    - Minimal required fields
    - Rich evidence dictionary
    - Normalized across all entry points (MCP/Proxy/SDK)
    - Immutable after creation
    """
    # Core identification
    egress: EgressType
    action: str  # e.g., "http.request", "fs.write", "exec.subprocess"
    target: str  # e.g., "api.openai.com", "/etc/passwd", "/bin/bash"
    
    # Execution context
    run_id: str
    step_id: str
    tool_name: str
    
    # Decision
    decision: PolicyDecision = PolicyDecision.ALLOW
    risk: RiskLevel = RiskLevel.LOW
    
    # Rich evidence
    evidence: Dict[str, Any] = field(default_factory=dict)
    # Expected evidence keys:
    # - usage: Dict (tokens, cost) for COST egress
    # - dlp_hits: List[str] for DLP detections
    # - taint_source: str for taint tracking
    # - request_summary: Dict for NETWORK
    # - file_path: str for FS
    # - command: str for EXEC
    
    # Metadata
    timestamp: datetime = field(default_factory=utc_now)
    summary: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for trace/storage"""
        return {
            "egress": self.egress.value,
            "action": self.action,
            "target": self.target,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "decision": self.decision.value,
            "risk": self.risk.value,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
        }


__all__ = ["EgressEvent", "EgressType", "PolicyDecision", "RiskLevel"]
