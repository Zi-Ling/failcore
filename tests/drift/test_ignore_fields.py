# tests/drift/test_ignore_fields.py
"""
Ignore Fields Tests - test field filtering during normalization

Tests that ignored fields (dynamic fields like request_id, timestamp) are
properly excluded from drift detection, including nested paths.
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


def test_ignore_top_level_fields():
    """
    Test: Top-level ignore fields are excluded from drift
    
    request_id is in DEFAULT_IGNORE_FIELDS, so changing it should not cause drift.
    """
    events = build_trace_events([
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt", "request_id": "req1"}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt", "request_id": "req2"}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},  # request_id changed
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt", "request_id": "req3"}, "seq": 3, "ts": "2024-01-01T00:02:00Z"},  # request_id changed
    ])
    
    result = compute_drift(events)
    
    # request_id is in ignore_fields, so drift should be 0
    assert len(result.drift_points) == 3
    assert result.drift_points[0].drift_delta == 0.0  # Baseline
    assert result.drift_points[1].drift_delta == 0.0  # request_id ignored
    assert result.drift_points[2].drift_delta == 0.0  # request_id ignored
    
    # No inflection points
    assert len(result.inflection_points) == 0


def test_ignore_nested_fields():
    """
    Test: Nested ignore fields should be excluded (if supported)
    
    Real-world tool params often have nested structures like:
    - headers.x-request-id
    - meta.request_id
    - request.id
    
    Current implementation: ignore_fields only applies to top-level keys.
    This test documents current behavior and can be updated if nested ignore is added.
    """
    events = build_trace_events([
        {"tool": "http_request", "params": {"url": "https://api.example.com", "headers": {"x-request-id": "req1"}}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
        {"tool": "http_request", "params": {"url": "https://api.example.com", "headers": {"x-request-id": "req2"}}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},  # x-request-id changed
    ])
    
    result = compute_drift(events)
    
    # Note: Current implementation only ignores top-level fields
    # So headers.x-request-id change will cause drift (value_changed)
    # This test documents current behavior
    assert len(result.drift_points) == 2
    assert result.drift_points[0].drift_delta == 0.0  # Baseline
    # headers.x-request-id is nested, not top-level, so it's not ignored
    assert result.drift_points[1].drift_delta > 0.0  # Has drift (nested field not ignored)
    
    # If we add nested ignore support, this test should be updated to expect drift_delta == 0.0


def test_ignore_multiple_fields():
    """
    Test: Multiple ignore fields are all excluded
    """
    events = build_trace_events([
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt", "request_id": "req1", "timestamp": "2024-01-01T00:00:00Z"}, "seq": 1, "ts": "2024-01-01T00:00:00Z"},
        {"tool": "test_tool", "params": {"path": "/tmp/test.txt", "request_id": "req2", "timestamp": "2024-01-01T00:01:00Z"}, "seq": 2, "ts": "2024-01-01T00:01:00Z"},  # Both changed
    ])
    
    result = compute_drift(events)
    
    # Both request_id and timestamp are ignored, so drift should be 0
    assert len(result.drift_points) == 2
    assert result.drift_points[0].drift_delta == 0.0  # Baseline
    assert result.drift_points[1].drift_delta == 0.0  # Both fields ignored


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
