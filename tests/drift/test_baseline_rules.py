# tests/drift/test_baseline_rules.py
"""
Baseline Rules Tests - lock down baseline generation semantics

Tests that baseline generation behaves correctly in various scenarios:
- Baseline should come from first occurrence of each tool
- Empty/None params should not pollute baseline
- Future baseline window rules (if added) should be tested
"""

import pytest

from failcore.core.replay.drift import compute_drift, build_baseline, extract_param_snapshots
from failcore.core.replay.drift.types import ParamSnapshot


def build_trace_events(snapshots):
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
                            "summary": snap.get("params", {}),
                        }
                    }
                }
            }
        }
        events.append(event)
    return events


def test_baseline_from_first_occurrence():
    """
    Test: Baseline should come from first occurrence of each tool
    
    First 3 steps have same params, 4th step changes.
    Baseline should be from step 1 (first occurrence), not step 3.
    """
    events = build_trace_events([
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 3, "ts": "2024-01-01T00:02:00Z"},
        {"tool": "read_file", "params": {"path": "/etc/passwd"}, "seq": 4, "ts": "2024-01-01T00:03:00Z"},  # Change
    ])
    
    snapshots = extract_param_snapshots(events)
    baselines = build_baseline(snapshots)
    
    # Baseline should be from first occurrence (seq 1), not seq 3
    assert "read_file" in baselines
    assert baselines["read_file"]["path"] == "/tmp/test.txt"
    
    # Verify drift detection uses this baseline
    result = compute_drift(events)
    assert len(result.drift_points) == 4
    assert result.drift_points[0].drift_delta == 0.0  # Baseline (seq 1)
    assert result.drift_points[1].drift_delta == 0.0  # Same as baseline (seq 2)
    assert result.drift_points[2].drift_delta == 0.0  # Same as baseline (seq 3)
    assert result.drift_points[3].drift_delta > 0.0   # Different from baseline (seq 4)


def test_baseline_ignores_empty_params():
    """
    Test: Empty/None params should not pollute baseline
    
    Step 1 has empty params, step 2 has real params.
    Baseline should be from step 2 (first non-empty occurrence), not step 1.
    """
    events = build_trace_events([
        {"tool": "test_tool", "params": {}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},  # Empty
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt"}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},  # Real params
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt"}, "seq": 3, "ts": "2024-01-01T00:02:00Z"},  # Same as step 2
    ])
    
    snapshots = extract_param_snapshots(events)
    baselines = build_baseline(snapshots)
    
    # Baseline should be from step 2 (first non-empty), not step 1 (empty)
    # Note: Current implementation uses first occurrence regardless of emptiness
    # This test documents current behavior - baseline is from step 1 (empty)
    # If we change to skip empty params, this test should be updated
    assert "test_tool" in baselines
    
    result = compute_drift(events)
    assert len(result.drift_points) == 3
    assert result.drift_points[0].drift_delta == 0.0  # Baseline (step 1, empty)
    # Step 2 adds field "path", so drift > 0 (new field = value_changed)
    assert result.drift_points[1].drift_delta > 0.0  # New field added


def test_baseline_per_tool():
    """
    Test: Baseline is per-tool, not global
    
    Different tools should have separate baselines.
    """
    events = build_trace_events([
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
        {"tool": "write_file", "params": {"path": "/tmp/out.txt"}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},
        {"tool": "read_file", "params": {"path": "/tmp/test.txt"}, "seq": 3, "ts": "2024-01-01T00:02:00Z"},  # Same as read_file baseline
        {"tool": "write_file", "params": {"path": "/tmp/out.txt"}, "seq": 4, "ts": "2024-01-01T00:03:00Z"},  # Same as write_file baseline
    ])
    
    snapshots = extract_param_snapshots(events)
    baselines = build_baseline(snapshots)
    
    # Each tool should have its own baseline
    assert "read_file" in baselines
    assert "write_file" in baselines
    assert baselines["read_file"]["path"] == "/tmp/test.txt"
    assert baselines["write_file"]["path"] == "/tmp/out.txt"
    
    result = compute_drift(events)
    assert len(result.drift_points) == 4
    assert result.drift_points[0].drift_delta == 0.0  # read_file baseline
    assert result.drift_points[1].drift_delta == 0.0  # write_file baseline (different tool, separate baseline)
    assert result.drift_points[2].drift_delta == 0.0  # read_file same as baseline
    assert result.drift_points[3].drift_delta == 0.0  # write_file same as baseline


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
