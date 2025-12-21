# failcore/cli/views/replay_run.py
"""
ReplayRunView - View model for replay execution results
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ReplayDecision(str, Enum):
    """Replay decision for a step"""
    HIT = "HIT"
    MISS = "MISS"
    SKIP = "SKIP"
    DIFF = "DIFF"


@dataclass
class ReplayStepNote:
    """A notable event during replay (policy deny, output mismatch, etc)"""
    type: str  # POLICY_DENIED | OUTPUT_MISMATCH | DIFF
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ReplayStepView:
    """Single step in replay execution"""
    ordinal: int  # 1, 2, 3...
    step_id: str
    tool: str
    attempt: int
    historical_status: str  # OK | FAIL | BLOCKED
    replay_decision: ReplayDecision
    replay_reason: Optional[str] = None
    fingerprint_id: Optional[str] = None
    notes: List[ReplayStepNote] = field(default_factory=list)
    injected: bool = False
    output_kind: Optional[str] = None


@dataclass
class ReplayRunSummary:
    """Summary statistics for replay run"""
    total_steps: int
    hits: int
    misses: int
    diffs: int
    policy_diffs: int
    output_diffs: int
    blocked: int
    ok: int
    failed: int
    hit_rate: str  # "66.7%"
    miss_rate: str
    diff_rate: str


@dataclass
class ReplayRunMeta:
    """Metadata about the replay run"""
    mode: str  # REPORT | MOCK | RESUME
    trace_path: str
    run_id: Optional[str] = None
    generated_at: Optional[str] = None


@dataclass
class ReplayRunFooter:
    """Footer information (next actions, hints)"""
    next_action: Optional[str] = None
    hints: List[str] = field(default_factory=list)


@dataclass
class ReplayRunView:
    """
    Complete view model for replay execution
    
    This is the stable, serializable structure that represents
    what happened during a replay run.
    """
    meta: ReplayRunMeta
    summary: ReplayRunSummary
    steps: List[ReplayStepView]
    footer: ReplayRunFooter
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "meta": {
                "mode": self.meta.mode,
                "trace_path": self.meta.trace_path,
                "run_id": self.meta.run_id,
                "generated_at": self.meta.generated_at,
            },
            "summary": {
                "total_steps": self.summary.total_steps,
                "hits": self.summary.hits,
                "misses": self.summary.misses,
                "diffs": self.summary.diffs,
                "policy_diffs": self.summary.policy_diffs,
                "output_diffs": self.summary.output_diffs,
                "hit_rate": self.summary.hit_rate,
                "miss_rate": self.summary.miss_rate,
                "diff_rate": self.summary.diff_rate,
            },
            "steps": [
                {
                    "ordinal": s.ordinal,
                    "step_id": s.step_id,
                    "tool": s.tool,
                    "attempt": s.attempt,
                    "historical_status": s.historical_status,
                    "replay_decision": s.replay_decision.value,
                    "replay_reason": s.replay_reason,
                    "fingerprint_id": s.fingerprint_id,
                    "notes": [
                        {"type": n.type, "message": n.message, "details": n.details}
                        for n in s.notes
                    ],
                    "injected": s.injected,
                    "output_kind": s.output_kind,
                }
                for s in self.steps
            ],
            "footer": {
                "next_action": self.footer.next_action,
                "hints": self.footer.hints,
            },
        }
