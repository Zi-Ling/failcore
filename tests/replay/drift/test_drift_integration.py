# tests/replay/test_drift_integration.py
"""
Drift Integration Tests - test drift detection in executor and replay

Tests the integrated drift flow:
1. Drift computation at RunEnd (automatic)
2. Lightweight drift detection in ReplayStage
"""

import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.executor.executor import Executor, ExecutorConfig
from failcore.core.tools.registry import ToolRegistry
from failcore.core.trace.recorder import JsonlTraceRecorder
from failcore.core.replay.replayer import Replayer, ReplayMode
from failcore.core.replay.drift import compute_drift


def build_test_trace_file(events: list) -> Path:
    """
    Build a temporary trace file from events
    
    Fixed: Use simple path-based approach to avoid fd double-close issues
    """
    fd, path = tempfile.mkstemp(suffix=".jsonl", prefix="test_trace_")
    # Close fd immediately to avoid double-close issues
    os.close(fd)
    
    # Write events using path-based open (simpler and more reliable)
    with open(path, 'w', encoding='utf-8') as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    
    return Path(path)


def build_trace_events(snapshots: list) -> list:
    """Build trace events from parameter snapshots"""
    events = []
    for snap in snapshots:
        event = {
            "seq": snap.get("seq", 0),
            "ts": snap.get("ts", "2024-01-01T00:00:00Z"),
            "event": {
                "type": "STEP_START",
                "step": {
                    "id": f"step_{snap.get('seq', 0)}",
                    "tool": snap.get("tool", "test_tool"),
                },
                "data": {
                    "payload": {
                        "input": {
                            "mode": "summary",
                            "raw": snap.get("params", {}),
                        }
                    }
                }
            },
            "run": {
                "run_id": "test-run",
                "created_at": "2024-01-01T00:00:00Z",
            }
        }
        events.append(event)
    return events


def test_drift_computed_at_run_end():
    """
    Integration truth:
    - close() runs automatically at context exit
    - close() sees an existing trace file at ctx.trace_path (or internal _trace_path)
    - close() computes drift and stores it on ctx (drift_result/_drift_result)
    """
    import json
    import os
    import tempfile
    from pathlib import Path
    from failcore.api import run

    events = build_trace_events([
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 1},
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 2},
        {"tool": "read_file", "params": {"path": "/etc/passwd"}, "seq": 3},
    ])

    # 1) Create a real trace file WITH test events (deterministic)
    fd, trace_path = tempfile.mkstemp(suffix=".jsonl", prefix="test_drift_")
    os.close(fd)
    trace_path = Path(trace_path)

    with open(trace_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    try:
        # 2) IMPORTANT: disable recorder writing (no pollution)
        #    Use whatever your run() supports: trace="off"/trace=False/trace=None
        with run(run_id="test-drift-runend", trace="off") as ctx:
            # 3) Point ctx to our prepared trace BEFORE close() happens.
            #    If you have a public setter, use it. Otherwise test-only hack:
            ctx._trace_path = str(trace_path)

            # no need to execute tools; we only test close()->compute_drift integration

        # 4) After exiting, close() has executed; drift should exist
        drift_result = getattr(ctx, "drift_result", None) or getattr(ctx, "_drift_result", None)
        assert drift_result is not None, "Drift should be computed automatically at close()"
        assert len(drift_result.drift_points) > 0

        domain_changes = [
            dp for dp in drift_result.drift_points
            if any(c.change_type == "domain_changed" for c in dp.top_changes)
        ]
        assert len(domain_changes) > 0, "Should detect domain change (/tmp -> /etc)"

    finally:
        if trace_path.exists():
            trace_path.unlink()


def test_drift_computation_idempotent():
    """
    Test: Drift computation is idempotent (only computes once)
    
    Scenario: close() is called multiple times
    Expected: Drift is only computed once
    """
    from failcore.api import run
    
    events = build_trace_events([
        {"tool": "test_tool", "params": {"x": 1}, "seq": 1},
        {"tool": "test_tool", "params": {"x": 2}, "seq": 2},
    ])
    
    trace_file = build_test_trace_file(events)
    
    try:
        with run(run_id="test-drift-idempotent", trace="auto") as ctx:
            # Set trace path for testing (test-only workaround)
            ctx._trace_path = str(trace_file)
        
        # First close (happens in __exit__)
        first_result = getattr(ctx, 'drift_result', None) or getattr(ctx, '_drift_result', None)
        
        # Manually call close() again
        ctx.close()
        
        # Should still be the same result (idempotent)
        second_result = getattr(ctx, 'drift_result', None) or getattr(ctx, '_drift_result', None)
        assert second_result is first_result, "Drift computation should be idempotent"
    finally:
        if trace_file.exists():
            trace_file.unlink()


def _extract_diff_details(event: dict) -> dict:
    """
    Extract diff_details from replay event with schema evolution support
    
    Supports multiple possible locations:
    - event["event"]["data"]["diff_details"] (current)
    - event["event"]["data"]["payload"]["diff_details"] (alternative)
    - event["event"]["data"]["replay"]["diff_details"] (alternative)
    """
    event_data = event.get("event", {}).get("data", {})
    
    # Try current location first
    if "diff_details" in event_data:
        return event_data["diff_details"]
    
    # Try alternative locations
    if "payload" in event_data and "diff_details" in event_data["payload"]:
        return event_data["payload"]["diff_details"]
    
    if "replay" in event_data and "diff_details" in event_data["replay"]:
        return event_data["replay"]["diff_details"]
    
    # Return empty dict if not found
    return {}


def test_replay_stage_lightweight_drift():
    """
    Test: ReplayStage performs lightweight drift detection
    
    Scenario: Replay HIT with parameter drift
    Expected: drift_changes detected and added to diff_details
    
    Fixed: Add assertions to verify drift is actually detected and stored
    Fixed: Use helper function to extract diff_details with schema evolution support
    """
    # Create baseline trace
    baseline_events = build_trace_events([
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 1},
    ])
    baseline_trace = build_test_trace_file(baseline_events)
    
    try:
        # Setup replayer
        replayer = Replayer(
            trace_path=str(baseline_trace),
            mode=ReplayMode.MOCK,
        )
        
        tools = ToolRegistry()
        def read_file(path: str):
            return {"content": "test"}
        tools.register("read_file", read_file)
        
        recorder = JsonlTraceRecorder()
        executor = Executor(
            tools=tools,
            recorder=recorder,
            replayer=replayer,
            config=ExecutorConfig(enable_cost_tracking=False),
        )
        
        ctx = RunContext(
            run_id="test-replay-drift",
            created_at=datetime.now(timezone.utc).isoformat(),
            sandbox_root="/tmp/test",
            cwd="/tmp/test",
        )
        
        # Step with parameter drift (path changed from /tmp/test.txt to /etc/passwd)
        step = Step(
            id="s1",
            tool="read_file",
            params={"path": "/etc/passwd"},  # Different from baseline (domain change)
        )
        
        result = executor.execute(step, ctx)
        
        # Should succeed (replay injected)
        assert result.status == StepStatus.OK, \
            f"Should succeed, got {result.status}"
        
        # Verify drift was detected in replay decision
        # Check for REPLAY_POLICY_DIFF or REPLAY_STEP_HIT events with params_drift
        replay_events = [
            e for e in recorder.events
            if isinstance(e, dict) and e.get("event", {}).get("type") in [
                "REPLAY_STEP_HIT",
                "REPLAY_POLICY_DIFF",
                "REPLAY_INJECTED",
            ]
        ]
        
        # At least one replay event should exist
        assert len(replay_events) > 0, "Should have replay event"
        
        # Check if any replay event contains params_drift in diff_details
        drift_detected = False
        for event in replay_events:
            # Use helper function to extract diff_details (schema evolution support)
            diff_details = _extract_diff_details(event)
            
            if "params_drift" in diff_details:
                drift_detected = True
                params_drift = diff_details["params_drift"]
                
                # Verify params_drift structure
                assert params_drift.get("drift") == True, "drift flag should be True"
                assert params_drift.get("delta") > 0, "drift delta should be positive"
                assert "changes" in params_drift, "should have changes list"
                assert len(params_drift.get("changes", [])) > 0, "should have at least one change"
                
                # Verify domain change was detected
                domain_changes = [
                    c for c in params_drift.get("changes", [])
                    if c.get("change_type") == "domain_changed"
                ]
                assert len(domain_changes) > 0, "Should detect domain change (path /tmp -> /etc)"
                break
        
        assert drift_detected, "Should detect params_drift in replay decision diff_details"
        
    finally:
        if baseline_trace.exists():
            baseline_trace.unlink()


def test_drift_baseline_from_trace():
    """
    Test: Drift baseline is extracted from trace itself
    
    Scenario: compute_drift() called on trace file
    Expected: Baseline is first occurrence of each tool's parameters
    """
    events = build_trace_events([
        {"tool": "read_file", "params": {"path": "/tmp/a.txt"}, "seq": 1},  # Baseline
        {"tool": "read_file", "params": {"path": "/tmp/b.txt"}, "seq": 2},  # Value change
        {"tool": "read_file", "params": {"path": "/etc/passwd"}, "seq": 3},  # Domain change
    ])
    
    trace_file = build_test_trace_file(events)
    
    try:
        # Compute drift
        drift_result = compute_drift(str(trace_file))
        
        # Verify baseline is from first step
        assert "read_file" in drift_result.baselines, "Should have baseline for read_file"
        baseline = drift_result.baselines["read_file"]
        assert baseline.get("path") == "/tmp/a.txt", "Baseline should be from first step"
        
        # Verify drift points
        assert len(drift_result.drift_points) == 3, "Should have 3 drift points"
        assert drift_result.drift_points[0].drift_delta == 0.0, "First step should have no drift (baseline)"
        assert drift_result.drift_points[1].drift_delta > 0.0, "Second step should have drift (value change)"
        assert drift_result.drift_points[2].drift_delta >= 5.0, "Third step should have high drift (domain change)"
        
    finally:
        if trace_file.exists():
            trace_file.unlink()


__all__ = [
    "test_drift_computed_at_run_end",
    "test_drift_computation_idempotent",
    "test_replay_stage_lightweight_drift",
    "test_drift_baseline_from_trace",
]
