# tests/drift/test_drift_points_shape.py
"""
Drift Points Shape Tests - verify output schema and semantics

Tests that drift points have correct structure and semantic meaning:
- drift_delta: drift score for this step (relative to baseline)
- drift_cumulative: cumulative drift score up to this step
"""

import pytest

from failcore.core.replay.drift import compute_drift


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


def test_drift_delta_semantics():
    """
    Test: drift_delta is "this step vs baseline", not cumulative
    
    drift_delta should represent the drift score for this specific step
    compared to the baseline, not cumulative.
    """
    events = build_trace_events([
        {"tool": "test_tool", "params": {"timeout": 1}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
        {"tool": "test_tool", "params": {"timeout": 5}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},  # 5x change (drift_delta = 2.0)
        {"tool": "test_tool", "params": {"timeout": 5}, "seq": 3, "ts": "2024-01-01T00:02:00Z"},  # Same as step 2 (drift_delta = 2.0, not 4.0)
    ])
    
    result = compute_drift(events)
    
    assert len(result.drift_points) == 3
    
    # drift_delta is per-step (vs baseline), not cumulative
    assert result.drift_points[0].drift_delta == 0.0   # Baseline: no drift
    assert result.drift_points[1].drift_delta == 2.0   # Step 2: magnitude_changed weight = 2.0
    assert result.drift_points[2].drift_delta == 2.0   # Step 3: same params as step 2, same drift vs baseline
    
    # drift_delta should be the same for steps with same params (both vs baseline)
    assert result.drift_points[1].drift_delta == result.drift_points[2].drift_delta


def test_drift_cumulative_semantics():
    """
    Test: drift_cumulative is sum of all drift_delta up to current step
    
    drift_cumulative should accumulate drift_delta values.
    """
    events = build_trace_events([
        {"tool": "test_tool", "params": {"timeout": 1}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
        {"tool": "test_tool", "params": {"timeout": 5}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},  # drift_delta = 2.0
        {"tool": "test_tool", "params": {"timeout": 5}, "seq": 3, "ts": "2024-01-01T00:02:00Z"},  # drift_delta = 2.0
    ])
    
    result = compute_drift(events)
    
    assert len(result.drift_points) == 3
    
    # drift_cumulative accumulates drift_delta
    assert result.drift_points[0].drift_cumulative == 0.0   # Step 1: 0.0
    assert result.drift_points[1].drift_cumulative == 2.0   # Step 2: 0.0 + 2.0 = 2.0
    assert result.drift_points[2].drift_cumulative == 4.0   # Step 3: 0.0 + 2.0 + 2.0 = 4.0
    
    # Verify cumulative = sum of deltas
    cumulative_expected = sum(dp.drift_delta for dp in result.drift_points[:3])
    assert result.drift_points[2].drift_cumulative == cumulative_expected


def test_drift_point_structure():
    """
    Test: DriftPoint has required fields with correct types
    """
    events = build_trace_events([
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt"}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
    ])
    
    result = compute_drift(events)
    
    assert len(result.drift_points) == 1
    dp = result.drift_points[0]
    
    # Required fields
    assert hasattr(dp, 'seq')
    assert hasattr(dp, 'ts')
    assert hasattr(dp, 'tool')
    assert hasattr(dp, 'drift_delta')
    assert hasattr(dp, 'drift_cumulative')
    assert hasattr(dp, 'top_changes')
    
    # Types
    assert isinstance(dp.seq, int)
    assert isinstance(dp.ts, str)
    assert isinstance(dp.tool, str)
    assert isinstance(dp.drift_delta, (int, float))
    assert isinstance(dp.drift_cumulative, (int, float))
    assert isinstance(dp.top_changes, list)
    
    # Values
    assert dp.seq == 1
    assert dp.tool == "test_tool"
    assert dp.drift_delta == 0.0  # Baseline
    assert dp.drift_cumulative == 0.0  # Baseline


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
