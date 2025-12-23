# failcore/cli/views/trace_report.py
"""
TraceReportView - View model for HTML execution report
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json
from pathlib import Path


@dataclass
class ReportStepView:
    """Single step in report"""
    step_id: str
    tool: str
    status: str
    duration_ms: int
    params: Dict[str, Any]
    output_value: Optional[Any] = None
    output_kind: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    has_policy_denied: bool = False
    has_output_normalized: bool = False
    replay_reused: bool = False
    # Policy details
    policy_id: Optional[str] = None
    rule_id: Optional[str] = None
    policy_reason: Optional[str] = None
    # Output normalization details
    expected_kind: Optional[str] = None
    observed_kind: Optional[str] = None
    normalize_reason: Optional[str] = None
    # Warnings list
    warnings: List[str] = field(default_factory=list)


@dataclass
class ReportSummary:
    """Summary statistics for report"""
    total_steps: int
    status_counts: Dict[str, int]
    total_duration_ms: int
    replay_reused: int
    artifacts_count: int = 0


@dataclass
class ReportValueMetrics:
    """Value/impact metrics"""
    unsafe_actions_blocked: int
    side_effects_occurred: int
    trace_recorded: bool = True


@dataclass
class ReportMeta:
    """Metadata about the report"""
    run_id: str
    created_at: str
    workspace: Optional[str] = None
    trace_path: Optional[str] = None
    overall_status: str = "OK"


@dataclass
class TraceReportView:
    """
    Complete view model for HTML execution report
    
    Represents a full execution report with metrics and timeline.
    """
    meta: ReportMeta
    summary: ReportSummary
    value_metrics: ReportValueMetrics
    steps: List[ReportStepView]
    failures: List[ReportStepView] = field(default_factory=list)
    warnings: List[ReportStepView] = field(default_factory=list)
    policy_details: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "meta": {
                "run_id": self.meta.run_id,
                "created_at": self.meta.created_at,
                "workspace": self.meta.workspace,
                "trace_path": self.meta.trace_path,
                "overall_status": self.meta.overall_status,
            },
            "summary": {
                "total_steps": self.summary.total_steps,
                "status_counts": self.summary.status_counts,
                "total_duration_ms": self.summary.total_duration_ms,
                "replay_reused": self.summary.replay_reused,
                "artifacts_count": self.summary.artifacts_count,
            },
            "value_metrics": {
                "unsafe_actions_blocked": self.value_metrics.unsafe_actions_blocked,
                "side_effects_occurred": self.value_metrics.side_effects_occurred,
                "trace_recorded": self.value_metrics.trace_recorded,
            },
            "steps": [
                {
                    "step_id": s.step_id,
                    "tool": s.tool,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "params": s.params,
                    "output_value": s.output_value,
                    "output_kind": s.output_kind,
                    "error_code": s.error_code,
                    "error_message": s.error_message,
                    "has_policy_denied": s.has_policy_denied,
                    "has_output_normalized": s.has_output_normalized,
                    "replay_reused": s.replay_reused,
                }
                for s in self.steps
            ],
            "failures": [
                {
                    "step_id": s.step_id,
                    "tool": s.tool,
                    "error_code": s.error_code,
                    "error_message": s.error_message,
                    "has_policy_denied": s.has_policy_denied,
                }
                for s in self.failures
            ],
        }


def build_report_view_from_trace(trace_path: Path) -> TraceReportView:
    """
    Build TraceReportView from trace file
    
    Args:
        trace_path: Path to trace.jsonl file
        
    Returns:
        TraceReportView with all data extracted and organized
    """
    # Read and parse trace
    events = []
    with open(trace_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    if not events:
        raise ValueError(f"Empty trace file: {trace_path}")
    
    # Extract run metadata
    first_event = events[0]
    run_info = first_event.get("run", {})
    run_id = run_info.get("run_id", "unknown")
    created_at = run_info.get("created_at", "unknown")
    workspace = run_info.get("workspace", "")
    
    # Group events by step_id
    step_events = {}
    for event in events:
        evt = event.get("event", {})
        step = evt.get("step", {})
        step_id = step.get("id")
        
        if step_id:
            if step_id not in step_events:
                step_events[step_id] = []
            step_events[step_id].append(event)
    
    # Analyze each step
    steps = []
    total_duration_ms = 0
    status_counts = {"OK": 0, "BLOCKED": 0, "FAIL": 0}
    replay_reused = 0
    failures = []
    warnings_list = []
    unsafe_blocked = 0
    policy_details = []
    
    for step_id, evts in step_events.items():
        step_view = _analyze_step(step_id, evts)
        steps.append(step_view)
        
        if step_view.duration_ms:
            total_duration_ms += step_view.duration_ms
        
        status = step_view.status
        if status in status_counts:
            status_counts[status] += 1
        
        if step_view.replay_reused:
            replay_reused += 1
        
        # Collect failures (BLOCKED or FAIL)
        if status in ["BLOCKED", "FAIL"]:
            failures.append(step_view)
        
        # Collect warnings (OK but has warnings like OUTPUT_KIND_MISMATCH)
        if status == "OK" and (step_view.warnings or step_view.has_output_normalized):
            warnings_list.append(step_view)
        
        # Collect policy blocks with details
        if step_view.has_policy_denied:
            unsafe_blocked += 1
            if step_view.rule_id and step_view.policy_reason:
                policy_details.append({
                    "rule_id": step_view.rule_id,
                    "reason": step_view.policy_reason,
                    "policy_id": step_view.policy_id,
                })
    
    # Determine overall status (Priority: BLOCKED > FAIL > OK)
    overall_status = "OK"
    if status_counts.get("BLOCKED", 0) > 0:
        overall_status = "BLOCKED"
    elif status_counts.get("FAIL", 0) > 0:
        overall_status = "FAIL"
    
    # Build view
    meta = ReportMeta(
        run_id=run_id,
        created_at=created_at,
        workspace=workspace,
        trace_path=str(trace_path),
        overall_status=overall_status,
    )
    
    summary = ReportSummary(
        total_steps=len(steps),
        status_counts=status_counts,
        total_duration_ms=total_duration_ms,
        replay_reused=replay_reused,
        artifacts_count=0,
    )
    
    value_metrics = ReportValueMetrics(
        unsafe_actions_blocked=unsafe_blocked,
        side_effects_occurred=status_counts["OK"],
        trace_recorded=True,
    )
    
    return TraceReportView(
        meta=meta,
        summary=summary,
        value_metrics=value_metrics,
        steps=steps,
        failures=failures,
        warnings=warnings_list,
        policy_details=policy_details,
    )


def _analyze_step(step_id: str, events: List[Dict[str, Any]]) -> ReportStepView:
    """Analyze single step from its events"""
    
    start_evt = None
    end_evt = None
    policy_denied_evt = None
    output_normalized_evt = None
    
    for event in events:
        evt = event.get("event", {})
        evt_type = evt.get("type")
        
        if evt_type == "STEP_START":
            start_evt = evt
        elif evt_type == "STEP_END":
            end_evt = evt
        elif evt_type == "POLICY_DENIED":
            policy_denied_evt = evt
        elif evt_type == "OUTPUT_NORMALIZED":
            output_normalized_evt = evt
    
    # Extract basic info from STEP_START
    tool = ""
    params = {}
    if start_evt:
        step = start_evt.get("step", {})
        tool = step.get("tool", "")
        # Extract params from data.payload.input.summary
        data = start_evt.get("data", {})
        payload = data.get("payload", {})
        input_data = payload.get("input", {})
        params = input_data.get("summary", {})
    
    # Extract result from STEP_END
    status = "UNKNOWN"
    duration_ms = 0
    error_code = ""
    error_message = ""
    output_value = None
    output_kind = None
    warnings = []
    
    if end_evt:
        data = end_evt.get("data", {})
        result = data.get("result", {})
        
        status = result.get("status", "UNKNOWN")
        duration_ms = result.get("duration_ms", 0)
        warnings = result.get("warnings", [])
        
        # Extract error info
        error = result.get("error", {})
        if error:
            error_code = error.get("code", "")
            error_message = error.get("message", "")
        
        # Extract output info from data.payload.output
        payload = data.get("payload", {})
        output = payload.get("output", {})
        if output:
            output_kind = output.get("kind")
            output_value = output.get("summary")  # Use summary instead of full value
    
    # Extract policy details
    policy_id = None
    rule_id = None
    policy_reason = None
    if policy_denied_evt:
        data = policy_denied_evt.get("data", {})
        policy = data.get("policy", {})
        policy_id = policy.get("policy_id")
        rule_id = policy.get("rule_id")
        policy_reason = policy.get("reason")
    
    # Extract output normalization details
    expected_kind = None
    observed_kind = None
    normalize_reason = None
    if output_normalized_evt:
        data = output_normalized_evt.get("data", {})
        normalize = data.get("normalize", {})
        expected_kind = normalize.get("expected_kind")
        observed_kind = normalize.get("observed_kind")
        normalize_reason = normalize.get("reason")
    
    # Check replay
    replay_reused = False
    if end_evt:
        data = end_evt.get("data", {})
        result = data.get("result", {})
        meta = result.get("meta", {})
        replay_reused = meta.get("replay_reused", False)
    
    return ReportStepView(
        step_id=step_id,
        tool=tool,
        status=status,
        duration_ms=duration_ms,
        params=params,
        output_value=output_value,
        output_kind=output_kind,
        error_code=error_code,
        error_message=error_message,
        has_policy_denied=policy_denied_evt is not None,
        has_output_normalized=output_normalized_evt is not None,
        replay_reused=replay_reused,
        policy_id=policy_id,
        rule_id=rule_id,
        policy_reason=policy_reason,
        expected_kind=expected_kind,
        observed_kind=observed_kind,
        normalize_reason=normalize_reason,
        warnings=warnings,
    )

