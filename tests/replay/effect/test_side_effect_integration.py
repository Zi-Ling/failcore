# tests/replay/test_side_effect_integration.py
"""
Side-Effect Integration Tests - test two-phase side-effect handling in executor

Tests the integrated side-effect flow:
1. Pre-execution prediction and boundary check (PolicyStage)
2. Post-execution observation and recording (DispatchStage)
"""

from datetime import datetime, timezone

from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.executor.executor import Executor, ExecutorConfig
from failcore.core.tools.registry import ToolRegistry
from failcore.core.config.boundaries import get_boundary
from failcore.core.trace.recorder import TraceRecorder


class MockTraceRecorder(TraceRecorder):
    """Mock trace recorder that stores events in memory"""
    
    def __init__(self):
        self.events = []
        self._seq = 0
    
    def record(self, event):
        self.events.append(event.to_dict() if hasattr(event, 'to_dict') else event)
    
    def next_seq(self):
        self._seq += 1
        return self._seq


def test_side_effect_gate_blocks_before_execution():
    """
    Test: Side-effect boundary gate blocks execution before tool runs
    
    Scenario: Tool would perform FS_WRITE, but boundary only allows FS_READ
    Expected: Step is BLOCKED in PolicyStage, tool never executes
    """
    # Setup: read_only boundary (allows FS_READ, blocks FS_WRITE)
    boundary = get_boundary("read_only")
    
    # Register a write_file tool
    # Note: Side-effect detection is based on tool name and params heuristics
    # In real usage, tools would have explicit metadata declaring side-effects
    tools = ToolRegistry()
    def write_file(path: str, content: str):
        return {"success": True, "path": path}
    tools.register("write_file", write_file)
    
    recorder = MockTraceRecorder()
    
    # Create executor with side-effect boundary
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        side_effect_boundary=boundary,  # Enable boundary gate
    )
    
    ctx = RunContext(
        run_id="test-side-effect-gate",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step that would write file (should be blocked)
    step = Step(
        id="s1",
        tool="write_file",
        params={"path": "/tmp/output.txt", "content": "test"},
    )
    
    result = executor.execute(step, ctx)
    
    # Should be blocked by boundary gate
    assert result.status == StepStatus.BLOCKED, f"Should be BLOCKED, got {result.status}"
    assert result.error is not None, "Should have error"
    assert "SIDE_EFFECT_BOUNDARY_CROSSED" in result.error.error_code or "boundary" in result.error.error_code.lower(), \
        f"Error code should mention boundary, got {result.error.error_code}"
    
    # Verify predicted side-effects are recorded
    # (This would be in ExecutionState, but we can't access it directly)
    # Instead, verify POLICY_DENIED event was recorded
    policy_denied_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "POLICY_DENIED"
    ]
    assert len(policy_denied_events) > 0, "Should have POLICY_DENIED event"
    
    # Verify tool was never executed (no SIDE_EFFECT_APPLIED events)
    side_effect_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "SIDE_EFFECT_APPLIED"
    ]
    assert len(side_effect_events) == 0, "Tool should not execute, so no SIDE_EFFECT_APPLIED events"


def test_side_effect_gate_allows_execution():
    """
    Test: Side-effect boundary gate allows execution when side-effect is within boundary
    
    Scenario: Tool performs FS_READ, which is allowed by read_only boundary
    Expected: Step executes successfully, side-effect is recorded
    
    Note: Side-effect detection is heuristic-based (tool name + params).
    In production, tools should declare side-effects via metadata/spec.
    """
    # Setup: read_only boundary (allows FS_READ)
    boundary = get_boundary("read_only")
    
    # Register a read_file tool
    # The detection logic recognizes "read_file" as filesystem.read operation
    tools = ToolRegistry()
    def read_file(path: str):
        return {"content": "file content", "path": path}
    tools.register("read_file", read_file)
    
    recorder = MockTraceRecorder()
    
    # Create executor with side-effect boundary
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        side_effect_boundary=boundary,
    )
    
    ctx = RunContext(
        run_id="test-side-effect-gate-allow",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step that reads file (should be allowed)
    step = Step(
        id="s1",
        tool="read_file",
        params={"path": "/tmp/test.txt"},
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed
    assert result.status == StepStatus.OK, f"Should succeed, got {result.status}"
    
    # Verify side-effect was recorded (post-execution observation)
    # Note: This is heuristic-based detection, not runtime observation
    # In production, tools would declare side-effects explicitly
    side_effect_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "SIDE_EFFECT_APPLIED"
    ]
    assert len(side_effect_events) > 0, "Should have SIDE_EFFECT_APPLIED event"
    
    # Verify FS_READ was detected (heuristic-based on tool name "read_file")
    fs_read_events = [
        e for e in side_effect_events
        if e.get("event", {}).get("data", {}).get("side_effect", {}).get("type") == "filesystem.read"
    ]
    assert len(fs_read_events) > 0, "Should detect FS_READ side-effect (heuristic-based)"


def test_side_effect_gate_disabled_by_default():
    """
    Test: Side-effect boundary gate is disabled by default
    
    Scenario: Executor created without side_effect_boundary parameter
    Expected: Gate is None, no boundary checks performed
    """
    tools = ToolRegistry()
    def write_file(path: str, content: str):
        return {"success": True}
    tools.register("write_file", write_file)
    
    recorder = MockTraceRecorder()
    
    # Create executor WITHOUT side-effect boundary (default)
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        # side_effect_boundary=None (default)
    )
    
    # Verify gate is disabled
    assert executor.services.side_effect_gate is None, "Gate should be disabled by default"
    
    ctx = RunContext(
        run_id="test-gate-disabled",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step that would be blocked if gate was enabled
    step = Step(
        id="s1",
        tool="write_file",
        params={"path": "/tmp/output.txt", "content": "test"},
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed (no boundary check)
    assert result.status == StepStatus.OK, "Should succeed when gate is disabled"


def test_two_phase_side_effect_tracking():
    """
    Test: Two-phase side-effect tracking (prediction + observation)
    
    Scenario: Tool performs allowed side-effect
    Expected: 
    - Prediction in PolicyStage (gate checked, no denial = prediction allowed execution)
    - Observation in DispatchStage (SIDE_EFFECT_APPLIED event recorded)
    - Both phases complete successfully
    
    Verification strategy:
    - Prediction phase: Verify gate was active (boundary provided) AND no POLICY_DENIED event
      This proves prediction occurred and allowed execution
    - Observation phase: Verify SIDE_EFFECT_APPLIED event exists
      This proves observation occurred and recorded the side-effect
    
    Note: Side-effect detection is heuristic-based (tool name + params).
    In production, tools should declare side-effects via metadata/spec.
    """
    boundary = get_boundary("read_only")
    
    tools = ToolRegistry()
    def read_file(path: str):
        return {"content": "test", "path": path}
    tools.register("read_file", read_file)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        side_effect_boundary=boundary,  # Gate is enabled
    )
    
    # Verify gate is enabled (prediction phase will occur)
    assert executor.services.side_effect_gate is not None, "Gate should be enabled for prediction phase"
    
    ctx = RunContext(
        run_id="test-two-phase",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    step = Step(
        id="s1",
        tool="read_file",
        params={"path": "/tmp/test.txt"},
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed (prediction phase allowed it)
    assert result.status == StepStatus.OK, "Should succeed"
    
    # === Phase 1 Verification: Prediction Phase ===
    # Verify prediction phase occurred by checking:
    # 1. Gate is enabled (already verified above)
    # 2. No POLICY_DENIED event (gate allowed execution)
    # 3. STEP_START event exists (execution proceeded)
    
    policy_denied_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "POLICY_DENIED"
    ]
    assert len(policy_denied_events) == 0, \
        "Prediction phase should allow execution (no POLICY_DENIED event)"
    
    step_start_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "STEP_START"
    ]
    assert len(step_start_events) > 0, \
        "Prediction phase should allow execution to proceed (STEP_START exists)"
    
    # === Phase 2 Verification: Observation Phase ===
    # Verify observation phase occurred by checking:
    # 1. SIDE_EFFECT_APPLIED event exists
    # 2. Event contains correct side-effect type
    
    side_effect_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "SIDE_EFFECT_APPLIED"
    ]
    assert len(side_effect_events) > 0, \
        "Observation phase should record side-effect (SIDE_EFFECT_APPLIED event exists)"
    
    # Verify FS_READ was detected (heuristic-based on tool name "read_file")
    fs_read_events = [
        e for e in side_effect_events
        if e.get("event", {}).get("data", {}).get("side_effect", {}).get("type") == "filesystem.read"
    ]
    assert len(fs_read_events) > 0, \
        "Observation phase should detect FS_READ side-effect (heuristic-based)"
    
    # === Summary: Both phases verified ===
    # Prediction phase: ✅ Gate enabled + No denial + Execution proceeded
    # Observation phase: ✅ Side-effect recorded + Correct type detected


__all__ = [
    "test_side_effect_gate_blocks_before_execution",
    "test_side_effect_gate_allows_execution",
    "test_side_effect_gate_disabled_by_default",
    "test_two_phase_side_effect_tracking",
]
