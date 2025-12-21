# failcore/cli/replay_cmd.py
"""
Replay commands
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from failcore.core.replay import Replayer, ReplayMode
from failcore.cli.views.replay_run import (
    ReplayRunView,
    ReplayRunMeta,
    ReplayRunSummary,
    ReplayRunFooter,
    ReplayStepView,
    ReplayStepNote,
    ReplayDecision,
)
from failcore.cli.views.replay_diff import (
    ReplayDiffView,
    ReplayDiffMeta,
    ReplayDiffSummary,
    PolicyDeniedStep,
    OutputMismatchStep,
)
from failcore.cli.renderers.text import TextRenderer
from failcore.cli.renderers.json import JsonRenderer


def replay_trace(args):
    """
    Replay execution from trace
    
    Two modes:
    - report: Audit mode, show what would happen
    - mock: Simulation mode, actually inject outputs
    """
    trace_path = args.trace
    mode = ReplayMode(args.mode)
    run_id = args.run
    output_format = getattr(args, 'format', 'text')
    
    if not Path(trace_path).exists():
        print(f"Error: Trace file not found: {trace_path}")
        return 1
    
    # Create replayer
    replayer = Replayer(trace_path, mode=mode, run_id=run_id)
    
    # Get all steps from trace
    steps = replayer.loader.get_all_steps()
    
    if not steps:
        print("No steps found in trace")
        return 1
    
    # Build view
    view = _build_replay_run_view(replayer, steps, trace_path, mode, run_id)
    
    # Render
    renderer = JsonRenderer() if output_format == 'json' else TextRenderer()
    output = renderer.render_replay_run(view)
    print(output)
    
    return 0


def _build_replay_run_view(
    replayer: Replayer,
    steps: list,
    trace_path: str,
    mode: ReplayMode,
    run_id: str = None,
) -> ReplayRunView:
    """Build ReplayRunView from replay results"""
    
    # Build step views
    step_views = []
    for idx, step_info in enumerate(steps, 1):
        step_view = _build_step_view(idx, step_info, mode)
        step_views.append(step_view)
    
    # Get stats
    stats = replayer.get_stats()
    
    # Build summary
    summary = ReplayRunSummary(
        total_steps=stats['total_steps'],
        hits=stats['hits'],
        misses=stats['misses'],
        diffs=stats['diffs'],
        policy_diffs=stats.get('policy_diffs', 0),
        output_diffs=stats.get('output_diffs', 0),
        blocked=sum(1 for s in step_views if s.historical_status == "BLOCKED"),
        ok=sum(1 for s in step_views if s.historical_status == "OK"),
        failed=sum(1 for s in step_views if s.historical_status == "FAIL"),
        hit_rate=stats.get('hit_rate', '0%'),
        miss_rate=stats.get('miss_rate', '0%'),
        diff_rate=stats.get('diff_rate', '0%'),
    )
    
    # Build meta
    meta = ReplayRunMeta(
        mode=mode.value,
        trace_path=trace_path,
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    
    # Build footer
    footer = ReplayRunFooter()
    
    # Add hints
    if mode == ReplayMode.REPORT:
        footer.hints.append("Run with --mode mock to inject outputs")
    
    # Check for misses
    first_miss = next((s for s in step_views if s.replay_decision == ReplayDecision.MISS), None)
    if first_miss:
        footer.next_action = f"MISS at {first_miss.step_id}, stopped"
    
    return ReplayRunView(
        meta=meta,
        summary=summary,
        steps=step_views,
        footer=footer,
    )


def _build_step_view(idx: int, step_info: dict, mode: ReplayMode) -> ReplayStepView:
    """Build ReplayStepView from step info"""
    step_id = step_info["step_id"]
    tool = step_info["tool"]
    
    # Extract info from start event
    start_evt = step_info.get("start_event", {})
    fingerprint_id = None
    if start_evt:
        evt_data = start_evt.get("event", {})
        step_data = evt_data.get("step", {})
        fingerprint = step_data.get("fingerprint", {})
        fingerprint_id = fingerprint.get("id")
    
    # Get end event info
    end_evt = step_info.get("end_event", {})
    status = "INCOMPLETE"
    if end_evt:
        end_data = end_evt.get("event", {}).get("data", {})
        result = end_data.get("result", {})
        status = result.get("status", "UNKNOWN")
    
    # Determine replay decision (simplified - in real execution this comes from executor)
    replay_decision = ReplayDecision.SKIP if mode == ReplayMode.REPORT else ReplayDecision.HIT
    
    # Collect notes
    notes = []
    for other_evt in step_info.get("other_events", []):
        other_evt_data = other_evt.get("event", {})
        evt_type = other_evt_data.get("type")
        
        if evt_type == "POLICY_DENIED":
            policy_data = other_evt_data.get("data", {}).get("policy", {})
            notes.append(ReplayStepNote(
                type="POLICY_DENIED",
                message=f"Historical: DENIED - {policy_data.get('reason')}",
            ))
        
        elif evt_type == "OUTPUT_NORMALIZED":
            norm_data = other_evt_data.get("data", {}).get("normalize", {})
            if norm_data.get("decision") == "mismatch":
                notes.append(ReplayStepNote(
                    type="OUTPUT_MISMATCH",
                    message=f"Kind mismatch: {norm_data.get('expected_kind')} -> {norm_data.get('observed_kind')}",
                ))
    
    return ReplayStepView(
        ordinal=idx,
        step_id=step_id,
        tool=tool,
        attempt=1,
        historical_status=status,
        replay_decision=replay_decision,
        fingerprint_id=fingerprint_id,
        notes=notes,
    )


def replay_diff(args):
    """
    Show diffs between current rules and historical execution
    
    Useful for policy validation and regression testing
    """
    trace_path = args.trace
    output_format = getattr(args, 'format', 'text')
    
    if not Path(trace_path).exists():
        print(f"Error: Trace file not found: {trace_path}")
        return 1
    
    # Create replayer in report mode
    replayer = Replayer(trace_path, mode=ReplayMode.REPORT)
    
    # Get all steps
    steps = replayer.loader.get_all_steps()
    
    # Build view
    view = _build_replay_diff_view(steps, trace_path)
    
    # Render
    renderer = JsonRenderer() if output_format == 'json' else TextRenderer()
    output = renderer.render_replay_diff(view)
    print(output)
    
    return 0


def _build_replay_diff_view(steps: list, trace_path: str) -> ReplayDiffView:
    """Build ReplayDiffView from trace analysis"""
    
    # Find steps with policy denials
    policy_denied = []
    output_mismatch = []
    
    for step_info in steps:
        step_id = step_info["step_id"]
        tool = step_info["tool"]
        
        # Check for policy denials
        for evt in step_info.get("other_events", []):
            evt_data = evt.get("event", {})
            if evt_data.get("type") == "POLICY_DENIED":
                policy_data = evt_data.get("data", {}).get("policy", {})
                policy_denied.append(PolicyDeniedStep(
                    step_id=step_id,
                    tool=tool,
                    reason=policy_data.get("reason", "Unknown"),
                    rule_id=policy_data.get("rule_id"),
                ))
                break
        
        # Check for output normalization issues
        for evt in step_info.get("other_events", []):
            evt_data = evt.get("event", {})
            if evt_data.get("type") == "OUTPUT_NORMALIZED":
                norm_data = evt_data.get("data", {}).get("normalize", {})
                if norm_data.get("decision") == "mismatch":
                    output_mismatch.append(OutputMismatchStep(
                        step_id=step_id,
                        tool=tool,
                        expected_kind=norm_data.get("expected_kind", "unknown"),
                        observed_kind=norm_data.get("observed_kind", "unknown"),
                    ))
                    break
    
    # Build summary
    summary = ReplayDiffSummary(
        total_steps=len(steps),
        policy_denied_count=len(policy_denied),
        policy_diff_count=0,  # Counterfactual diffs would be calculated during actual replay
        output_mismatch_count=len(output_mismatch),
        fingerprint_miss_count=0,
    )
    
    # Build meta
    meta = ReplayDiffMeta(
        trace_path=trace_path,
        compare_target="historical vs current rules",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    
    return ReplayDiffView(
        meta=meta,
        summary=summary,
        policy_denied_steps=policy_denied,
        output_mismatch_steps=output_mismatch,
    )
