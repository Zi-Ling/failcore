# failcore/core/replay/replayer.py
"""
Core replay engine for deterministic execution simulation
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .loader import TraceLoader
from .matcher import FingerprintMatcher, MatchResult, MatchInfo
from ..step import StepResult, StepStatus, StepError, StepOutput, OutputKind


class ReplayMode(str, Enum):
    """Replay execution modes"""
    REPORT = "report"  # audit mode - only report, no execution
    MOCK = "mock"  # Simulation mode - inject historical outputs


class ReplayHitType(str, Enum):
    """Replay hit types"""
    HIT = "HIT"  # Fingerprint matched, output injected
    MISS = "MISS"  # Fingerprint mismatch, fallback to real execution
    DIFF = "DIFF"  # Matched but decision differs
    SKIP = "SKIP"  # Skipped (report mode)


@dataclass
class ReplayResult:
    """Result of replay attempt"""
    hit_type: ReplayHitType
    injected: bool
    step_result: Optional[StepResult] = None
    match_info: Optional[MatchInfo] = None
    diff_details: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class Replayer:
    """
    Replay engine for FailCore
    
    Provides three capabilities:
    1. Policy Replay - verify rule changes
    2. Logic Replay - zero-cost debugging
    3. Deterministic Replay - reproducible execution
    
    Two modes:
    - REPORT: audit mode, only report what would happen
    - MOCK: Simulation mode, inject historical outputs
    """
    
    def __init__(
        self,
        trace_path: str,
        mode: ReplayMode = ReplayMode.MOCK,
        run_id: Optional[str] = None,
    ):
        """
        Initialize replayer
        
        Args:
            trace_path: Path to trace file
            mode: Replay mode (report or mock)
            run_id: Optional run_id filter
        """
        self.trace_path = trace_path
        self.mode = mode
        self.run_id = run_id
        
        # Load trace
        self.loader = TraceLoader(trace_path)
        self.matcher = FingerprintMatcher()
        
        # Stats
        self.stats = {
            "total_steps": 0,
            "hits": 0,
            "misses": 0,
            "diffs": 0,
            "policy_diffs": 0,
            "output_diffs": 0,
        }
    
    def replay_step(
        self,
        step_id: str,
        tool: str,
        params: Dict[str, Any],
        fingerprint: Dict[str, Any],
        current_policy_decision: Optional[tuple] = None,
    ) -> ReplayResult:
        """
        Attempt to replay a step
        
        Args:
            step_id: Current step ID
            tool: Tool name
            params: Tool parameters
            fingerprint: Current fingerprint
            current_policy_decision: (allowed, reason) if policy was checked
            
        Returns:
            ReplayResult with hit/miss/diff information
        """
        self.stats["total_steps"] += 1
        
        # Find historical step by fingerprint
        fp_id = fingerprint.get("id")
        historical_step = self.loader.get_by_fingerprint(fp_id) if fp_id else None
        
        # Match fingerprint
        match_info = self.matcher.match(fingerprint, historical_step)
        
        if match_info.result == MatchResult.MISS:
            self.stats["misses"] += 1
            return ReplayResult(
                hit_type=ReplayHitType.MISS,
                injected=False,
                match_info=match_info,
                message=match_info.reason,
            )
        
        # Check for diffs
        diff_details = {}
        
        # Policy diff check
        if current_policy_decision and historical_step:
            policy_diff = self.matcher.check_policy_diff(
                current_policy_decision,
                historical_step
            )
            if policy_diff:
                diff_details["policy"] = policy_diff
                self.stats["policy_diffs"] += 1
        
        # If we have diffs, mark as DIFF
        if diff_details:
            self.stats["diffs"] += 1
            
            # In report mode, don't inject
            if self.mode == ReplayMode.REPORT:
                return ReplayResult(
                    hit_type=ReplayHitType.DIFF,
                    injected=False,
                    match_info=match_info,
                    diff_details=diff_details,
                    message="Policy decision differs from historical",
                )
        
        # HIT - can inject output
        self.stats["hits"] += 1
        
        # In report mode, don't actually inject
        if self.mode == ReplayMode.REPORT:
            return ReplayResult(
                hit_type=ReplayHitType.SKIP,
                injected=False,
                match_info=match_info,
                diff_details=diff_details if diff_details else None,
                message="Report mode - would inject historical output",
            )
        
        # MOCK mode - inject historical output
        step_result = self._inject_output(historical_step, step_id, tool)
        
        return ReplayResult(
            hit_type=ReplayHitType.HIT,
            injected=True,
            step_result=step_result,
            match_info=match_info,
            diff_details=diff_details if diff_details else None,
            message="Injected historical output",
        )
    
    def _inject_output(
        self,
        historical_step: Dict[str, Any],
        step_id: str,
        tool: str,
    ) -> StepResult:
        """
        Inject historical output as step result
        
        Creates a StepResult from historical trace data
        """
        end_evt = historical_step.get("end_event")
        
        if not end_evt:
            # No end event - create incomplete result
            return StepResult(
                step_id=step_id,
                tool=tool,
                status=StepStatus.FAIL,
                started_at="",
                finished_at="",
                duration_ms=0,
                output=None,
                error=StepError(
                    error_code="REPLAY_INCOMPLETE",
                    message="Historical step has no end event",
                ),
                meta={"replay": True, "replay_source": "incomplete"},
            )
        
        # Extract result from end event
        end_data = end_evt.get("event", {}).get("data", {})
        result = end_data.get("result", {})
        
        status = result.get("status", "UNKNOWN")
        duration_ms = result.get("duration_ms", 0)
        
        # Map status string to enum
        try:
            status_enum = StepStatus(status.lower())
        except ValueError:
            status_enum = StepStatus.FAIL
        
        # Extract output
        output = None
        payload = end_data.get("payload", {})
        if payload:
            output_data = payload.get("output", {})
            if output_data:
                kind_str = output_data.get("kind", "unknown")
                value = output_data.get("summary")
                
                try:
                    kind = OutputKind(kind_str)
                except ValueError:
                    kind = OutputKind.UNKNOWN
                
                output = StepOutput(kind=kind, value=value)
        
        # Extract error
        error = None
        error_data = result.get("error")
        if error_data:
            error = StepError(
                error_code=error_data.get("code", "UNKNOWN"),
                message=error_data.get("message", ""),
                detail=error_data.get("detail"),
            )
        
        return StepResult(
            step_id=step_id,
            tool=tool,
            status=status_enum,
            started_at=end_evt.get("ts", ""),
            finished_at=end_evt.get("ts", ""),
            duration_ms=duration_ms,
            output=output,
            error=error,
            meta={
                "replay": True,
                "replay_source": "injected",
                "replay_fingerprint": historical_step.get("start_event", {})
                    .get("event", {})
                    .get("step", {})
                    .get("fingerprint", {})
                    .get("id"),
            },
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get replay statistics"""
        total = self.stats["total_steps"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "hit_rate": f"{self.stats['hits'] / total * 100:.1f}%",
            "miss_rate": f"{self.stats['misses'] / total * 100:.1f}%",
            "diff_rate": f"{self.stats['diffs'] / total * 100:.1f}%",
        }
