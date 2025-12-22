# failcore/cli/views/replay_diff.py
"""
ReplayDiffView - View model for replay diff analysis (counterfactual comparison)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class PolicyDeniedStep:
    """A step that was denied by policy"""
    step_id: str
    tool: str
    reason: str
    rule_id: Optional[str] = None


@dataclass
class OutputMismatchStep:
    """A step with output kind mismatch"""
    step_id: str
    tool: str
    expected_kind: str
    observed_kind: str
    sample: Optional[str] = None


@dataclass
class DiffEntry:
    """A difference between historical and current execution"""
    type: str  # POLICY_DIFF | OUTPUT_DIFF | NORMALIZE_DIFF
    step_id: str
    tool: str
    before: str  # Historical value
    after: str  # Current value
    reason: Optional[str] = None


@dataclass
class ReplayDiffSummary:
    """Summary of diff analysis"""
    total_steps: int
    policy_denied_count: int
    policy_diff_count: int
    output_mismatch_count: int
    fingerprint_miss_count: int


@dataclass
class ReplayDiffMeta:
    """Metadata for diff analysis"""
    trace_path: str
    run_id: Optional[str] = None
    compare_target: str = "historical vs current rules"
    generated_at: Optional[str] = None


@dataclass
class ReplayDiffView:
    """
    Complete view model for replay diff analysis
    
    Shows what would change if rules/parsers changed.
    This is the "counterfactual" analysis view.
    """
    meta: ReplayDiffMeta
    summary: ReplayDiffSummary
    policy_denied_steps: List[PolicyDeniedStep]
    output_mismatch_steps: List[OutputMismatchStep]
    diffs: List[DiffEntry] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "meta": {
                "trace_path": self.meta.trace_path,
                "run_id": self.meta.run_id,
                "compare_target": self.meta.compare_target,
                "generated_at": self.meta.generated_at,
            },
            "summary": {
                "total_steps": self.summary.total_steps,
                "policy_denied_count": self.summary.policy_denied_count,
                "policy_diff_count": self.summary.policy_diff_count,
                "output_mismatch_count": self.summary.output_mismatch_count,
                "fingerprint_miss_count": self.summary.fingerprint_miss_count,
            },
            "policy_denied_steps": [
                {
                    "step_id": s.step_id,
                    "tool": s.tool,
                    "reason": s.reason,
                    "rule_id": s.rule_id,
                }
                for s in self.policy_denied_steps
            ],
            "output_mismatch_steps": [
                {
                    "step_id": s.step_id,
                    "tool": s.tool,
                    "expected_kind": s.expected_kind,
                    "observed_kind": s.observed_kind,
                    "sample": s.sample,
                }
                for s in self.output_mismatch_steps
            ],
            "diffs": [
                {
                    "type": d.type,
                    "step_id": d.step_id,
                    "tool": d.tool,
                    "before": d.before,
                    "after": d.after,
                    "reason": d.reason,
                }
                for d in self.diffs
            ],
        }
