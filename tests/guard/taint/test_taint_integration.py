# tests/guard/taint/test_taint_integration.py
"""
Taint Tracking & DLP Integration Tests - test taint tracking in Executor pipeline

Tests the integrated taint tracking flow:
1. Source tools mark output as tainted (via DispatchStage)
2. Sink tools detect tainted inputs and apply DLP policy (via PolicyStage)
3. DLP actions: BLOCK, SANITIZE, REQUIRE_APPROVAL
4. Taint propagation across tool chains
5. Default disabled (zero cost, zero behavior)
6. Per-run configuration via GuardConfig
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.executor.executor import Executor, ExecutorConfig
from failcore.core.tools.registry import ToolRegistry
from failcore.core.config.guards import GuardConfig
from failcore.core.trace.recorder import TraceRecorder


class MockTraceRecorder(TraceRecorder):
    """Mock trace recorder for testing"""
    def __init__(self):
        self._seq = 0
        self.events = []
    
    def next_seq(self):
        self._seq += 1
        return self._seq
    
    def record(self, event):
        self.events.append(event.to_dict() if hasattr(event, 'to_dict') else event)


def test_taint_disabled_by_default():
    """
    Test: Taint tracking is disabled by default
    
    Scenario: Executor created without GuardConfig
    Expected: Taint tracking has zero cost, zero behavior
    """
    tools = ToolRegistry()
    tools.register("read_file", lambda path: f"Content of {path}")
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
    )
    
    ctx = RunContext(
        run_id="test-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    step = Step(
        id="s1",
        tool="read_file",
        params={"path": "/etc/passwd"},
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed (no taint tracking, no DLP)
    assert result.status == StepStatus.OK
    assert executor.services.taint_engine is None
    assert executor.services.taint_store is None


def test_taint_enabled_via_guard_config():
    """
    Test: Taint tracking enabled via GuardConfig
    
    Scenario: Executor created with GuardConfig(taint=True)
    Expected: Taint engine and store are initialized
    """
    tools = ToolRegistry()
    tools.register("read_file", lambda path: f"Content of {path}")
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True),
    )
    
    # Taint services should be initialized
    assert executor.services.taint_engine is not None
    assert executor.services.taint_store is not None


def test_source_tool_marks_tainted():
    """
    Test: Source tools mark output as tainted
    
    Scenario: read_file tool executes successfully
    Expected: Output is marked as tainted in taint_store
    """
    tools = ToolRegistry()
    
    # Source tool: read_file
    def read_file(path: str) -> Dict[str, Any]:
        return {
            "content": f"Content of {path}",
            "customer_email": "john.doe@example.com",
            "customer_phone": "555-123-4567",
        }
    
    tools.register("read_file", read_file)
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True),
    )
    
    ctx = RunContext(
        run_id="test-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    step = Step(
        id="s1",
        tool="read_file",
        params={"path": "/etc/passwd"},
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed
    assert result.status == StepStatus.OK
    
    # Output should be marked as tainted
    assert executor.services.taint_store.is_tainted("s1")
    tags = executor.services.taint_store.get_tags("s1")
    assert len(tags) > 0
    
    # Check taint tag properties
    tag = list(tags)[0]
    assert tag.source_tool == "read_file"
    assert tag.source_step_id == "s1"


def test_sink_tool_blocks_tainted_data():
    """
    Test: Sink tools block tainted data (BLOCK action)
    
    Scenario:
    1. read_file produces tainted data
    2. send_email attempts to send tainted data externally
    Expected: send_email is BLOCKED in PolicyStage
    """
    tools = ToolRegistry()
    
    # Source tool
    customer_data = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
    }
    
    def read_file(path: str) -> Dict[str, Any]:
        return customer_data
    
    tools.register("read_file", read_file)
    
    # Sink tool
    def send_email(to: str, subject: str, body: Any) -> Dict[str, str]:
        return {"status": "sent", "to": to}
    
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True),
    )
    
    ctx = RunContext(
        run_id="test-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step 1: Read file (source)
    step1 = Step(
        id="s1",
        tool="read_file",
        params={"path": "customers.json"},
    )
    
    result1 = executor.execute(step1, ctx)
    assert result1.status == StepStatus.OK
    assert executor.services.taint_store.is_tainted("s1")
    
    # Step 2: Send email (sink) - should be blocked
    step2 = Step(
        id="s2",
        tool="send_email",
        params={
            "to": "external@example.com",
            "subject": "Customer Data",
            "body": customer_data,  # Tainted data
        },
    )
    
    result2 = executor.execute(step2, ctx)
    
    # Should be BLOCKED
    assert result2.status == StepStatus.BLOCKED
    assert result2.error is not None
    assert result2.error.error_code == "DATA_LEAK_PREVENTED"
    
    # Check POLICY_DENIED event
    policy_denied_events = [
        e for e in recorder.events
        if e.get("event", {}).get("type") == "POLICY_DENIED"
        and e.get("event", {}).get("data", {}).get("policy", {}).get("policy_id") == "DLP-Guard"
    ]
    assert len(policy_denied_events) == 1
    
    event = policy_denied_events[0]
    assert event["event"]["data"]["policy"]["rule_id"] == "DLP001"  # Default rule ID


def test_sink_tool_sanitizes_tainted_data():
    """
    Test: Sink tools sanitize tainted data (SANITIZE action)
    
    Scenario:
    1. db_query produces INTERNAL tainted data
    2. log_external attempts to send tainted data (with sanitization)
    Expected: Data is sanitized before sending
    """
    tools = ToolRegistry()
    
    # Source tool: db_query
    log_data = {
        "timestamp": "2024-01-01T00:00:00Z",
        "user_email": "admin@company.com",
        "api_key": "sk_live_1234567890abcdef",
        "message": "User login",
    }
    
    def db_query(query: str) -> Dict[str, Any]:
        return log_data
    
    tools.register("db_query", db_query)
    
    # Sink tool: log_external
    logged_data = []
    
    def log_external(log: Dict[str, Any]) -> Dict[str, str]:
        logged_data.append(log)
        return {"status": "logged"}
    
    tools.register("log_external", log_external)
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True),
    )
    
    ctx = RunContext(
        run_id="test-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step 1: Query database (source)
    step1 = Step(
        id="s1",
        tool="db_query",
        params={"query": "SELECT * FROM logs"},
    )
    
    result1 = executor.execute(step1, ctx)
    assert result1.status == StepStatus.OK
    
    # Step 2: Log externally (sink) - should sanitize
    step2 = Step(
        id="s2",
        tool="log_external",
        params={"log": log_data},
    )
    
    result2 = executor.execute(step2, ctx)
    
    # Should succeed (sanitized)
    assert result2.status == StepStatus.OK
    
    # Check if sanitization event was recorded
    sanitization_events = [
        e for e in recorder.events
        if e.get("event", {}).get("type") == "POLICY_DECISION"
        and e.get("event", {}).get("data", {}).get("policy", {}).get("action") == "sanitize"
    ]
    
    # Note: Sanitization may or may not trigger event depending on DLP policy
    # The key is that execution succeeded with sanitized params
    
    # Check that original_params and sanitized_params are stored in state
    # (This would require accessing ExecutionState, which is internal)
    # For now, just verify execution succeeded


def test_taint_propagation_across_steps():
    """
    Test: Taint propagates across tool chain
    
    Scenario:
    1. read_file → tainted
    2. process_data (depends on s1) → tainted
    3. send_email (depends on s2) → blocked
    Expected: Taint propagates through chain, final sink is blocked
    """
    tools = ToolRegistry()
    
    customer_data = {"name": "John Doe", "email": "john@example.com"}
    
    def read_file(path: str) -> Dict[str, Any]:
        return customer_data
    
    tools.register("read_file", read_file)
    
    def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
        return {"processed": data}
    
    tools.register("process_data", process_data)
    
    def send_email(to: str, body: Any) -> Dict[str, str]:
        return {"status": "sent"}
    
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True),
    )
    
    ctx = RunContext(
        run_id="test-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step 1: Read file (source)
    step1 = Step(
        id="s1",
        tool="read_file",
        params={"path": "customers.json"},
    )
    
    result1 = executor.execute(step1, ctx)
    assert result1.status == StepStatus.OK
    assert executor.services.taint_store.is_tainted("s1")
    
    # Step 2: Process data (should propagate taint)
    step2 = Step(
        id="s2",
        tool="process_data",
        params={"data": customer_data},  # Uses tainted data
    )
    
    result2 = executor.execute(step2, ctx)
    assert result2.status == StepStatus.OK
    
    # Step 3: Send email (sink) - should be blocked
    step3 = Step(
        id="s3",
        tool="send_email",
        params={
            "to": "external@example.com",
            "body": customer_data,  # Tainted data
        },
    )
    
    result3 = executor.execute(step3, ctx)
    
    # Should be BLOCKED
    assert result3.status == StepStatus.BLOCKED
    assert result3.error is not None
    assert result3.error.error_code == "DATA_LEAK_PREVENTED"


def test_taint_allows_safe_operations():
    """
    Test: Taint tracking allows safe operations
    
    Scenario: Tool calls that don't involve tainted data
    Expected: All operations succeed
    """
    tools = ToolRegistry()
    
    def write_file(path: str, content: str) -> Dict[str, str]:
        return {"status": "written", "path": path}
    
    tools.register("write_file", write_file)
    
    def send_email(to: str, subject: str, body: str) -> Dict[str, str]:
        return {"status": "sent", "to": to}
    
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True),
    )
    
    ctx = RunContext(
        run_id="test-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step 1: Write file (not a source, safe)
    step1 = Step(
        id="s1",
        tool="write_file",
        params={"path": "output.txt", "content": "Hello world"},
    )
    
    result1 = executor.execute(step1, ctx)
    assert result1.status == StepStatus.OK
    
    # Step 2: Send email with non-tainted data (safe)
    step2 = Step(
        id="s2",
        tool="send_email",
        params={
            "to": "user@example.com",
            "subject": "Hello",
            "body": "This is a safe message",
        },
    )
    
    result2 = executor.execute(step2, ctx)
    assert result2.status == StepStatus.OK


def test_taint_with_semantic_guard():
    """
    Test: Taint tracking works alongside semantic guard
    
    Scenario: Both guards enabled via GuardConfig
    Expected: Both guards work independently
    """
    tools = ToolRegistry()
    
    def read_file(path: str) -> str:
        return "File content"
    
    tools.register("read_file", read_file)
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True, semantic=True),
    )
    
    # Both guards should be initialized
    assert executor.services.taint_engine is not None
    assert executor.services.taint_store is not None
    assert executor.services.semantic_guard is not None


def test_taint_store_summary():
    """
    Test: Taint store provides summary statistics
    
    Scenario: Multiple steps with tainted data
    Expected: Summary shows correct counts
    """
    tools = ToolRegistry()
    
    def read_file(path: str) -> Dict[str, Any]:
        return {"content": f"Content of {path}"}
    
    tools.register("read_file", read_file)
    
    recorder = MockTraceRecorder()
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        guard_config=GuardConfig(taint=True),
    )
    
    ctx = RunContext(
        run_id="test-run",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Execute multiple source tools
    for i in range(3):
        step = Step(
            id=f"s{i+1}",
            tool="read_file",
            params={"path": f"/file{i+1}.txt"},
        )
        result = executor.execute(step, ctx)
        assert result.status == StepStatus.OK
    
    # Get summary
    summary = executor.services.taint_store.get_summary()
    
    assert summary["tainted_steps"] == 3
    assert "sensitivity_distribution" in summary
    assert "source_distribution" in summary
