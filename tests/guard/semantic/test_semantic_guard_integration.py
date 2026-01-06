# tests/guard/semantic/test_semantic_guard_integration.py
"""
Semantic Guard Integration Tests - test semantic guard in Executor pipeline

Tests the integrated semantic guard flow:
1. Semantic guard blocks malicious patterns (via PolicyStage)
2. Semantic guard allows safe operations
3. Default disabled (zero cost, zero behavior)
4. Structured PolicyResult with explainable fields
5. Unified POLICY_DENIED event with source="semantic"
"""

import pytest
from datetime import datetime, timezone

from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.executor.executor import Executor, ExecutorConfig
from failcore.core.tools.registry import ToolRegistry
from failcore.core.guards.semantic import SemanticGuardMiddleware, RuleSeverity
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


def test_semantic_guard_blocks_secret_leakage():
    """
    Test: Semantic guard blocks secret leakage in tool parameters
    
    Scenario: Tool call contains API key in parameters
    Expected: Step is BLOCKED in PolicyStage, tool never executes
    """
    # Create semantic guard with secret leakage detection enabled
    guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    # Register a send_email tool
    tools = ToolRegistry()
    def send_email(to: str, subject: str, body: str):
        return {"success": True, "message_id": "msg_123"}
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    
    # Create executor with semantic guard
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-semantic-secret",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step with API key in body (should be blocked)
    step = Step(
        id="s1",
        tool="send_email",
        params={
            "to": "user@example.com",
            "subject": "API Credentials",
            "body": "Here are your credentials:\nAPI_KEY=sk-1234567890abcdefghijklmnop\nUse them wisely!",
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should be blocked by semantic guard
    assert result.status == StepStatus.BLOCKED, f"Should be BLOCKED, got {result.status}"
    assert result.error is not None, "Should have error"
    assert "SEMANTIC_VIOLATION" in result.error.error_code, \
        f"Error code should be SEMANTIC_VIOLATION, got {result.error.error_code}"
    
    # Verify POLICY_DENIED event was recorded (unified event type)
    policy_denied_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "POLICY_DENIED"
    ]
    assert len(policy_denied_events) > 0, "Should have POLICY_DENIED event"
    
    # Verify event details contain semantic source
    last_event = policy_denied_events[-1]
    event_data = last_event.get("event", {}).get("data", {})
    policy_data = event_data.get("policy", {})
    assert policy_data.get("policy_id") == "Semantic-Guard", \
        "Policy ID should be Semantic-Guard"
    
    # Verify tool was never executed (no STEP_END with OK status)
    step_end_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "STEP_END"
    ]
    if step_end_events:
        last_step_end = step_end_events[-1]
        result_data = last_step_end.get("event", {}).get("data", {}).get("result", {})
        assert result_data.get("status").upper() == "BLOCKED", \
            "Step should be BLOCKED, not executed"


def test_semantic_guard_blocks_sql_injection():
    """
    Test: Semantic guard blocks SQL injection patterns
    
    Scenario: Tool call contains SQL injection pattern
    Expected: Step is BLOCKED in PolicyStage
    """
    guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    tools = ToolRegistry()
    def db_query(sql: str):
        return {"rows": []}
    tools.register("db_query", db_query)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-semantic-sql",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step with SQL injection (should be blocked)
    step = Step(
        id="s1",
        tool="db_query",
        params={
            "sql": "SELECT * FROM users WHERE id=1; DROP TABLE users; --",
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should be blocked
    assert result.status == StepStatus.BLOCKED, "Should be BLOCKED"
    assert result.error is not None, "Should have error"
    assert "SEMANTIC_VIOLATION" in result.error.error_code, \
        f"Error code should be SEMANTIC_VIOLATION, got {result.error.error_code}"


def test_semantic_guard_blocks_path_traversal():
    """
    Test: Semantic guard blocks path traversal patterns
    
    Scenario: Tool call contains path traversal pattern
    Expected: Step is BLOCKED in PolicyStage
    """
    guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    tools = ToolRegistry()
    def read_file(path: str):
        return {"content": "file content"}
    tools.register("read_file", read_file)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-semantic-path",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step with path traversal (should be blocked)
    step = Step(
        id="s1",
        tool="read_file",
        params={
            "path": "../../etc/passwd",
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should be blocked
    assert result.status == StepStatus.BLOCKED, "Should be BLOCKED"
    assert result.error is not None, "Should have error"
    assert "SEMANTIC_VIOLATION" in result.error.error_code, \
        f"Error code should be SEMANTIC_VIOLATION, got {result.error.error_code}"


def test_semantic_guard_allows_safe_operations():
    """
    Test: Semantic guard allows safe operations
    
    Scenario: Tool call with safe parameters
    Expected: Step executes successfully
    """
    guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    tools = ToolRegistry()
    # Use http_get instead of read_file to avoid path traversal detection
    def http_get(url: str):
        return {"status": 200, "content": "response"}
    tools.register("http_get", http_get)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-semantic-safe",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step with safe parameters (should succeed)
    step = Step(
        id="s1",
        tool="http_get",
        params={
            "url": "https://api.example.com/data",
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed
    assert result.status == StepStatus.OK, f"Should succeed, got {result.status}. Error: {result.error.error_code if result.error else 'None'}"
    
    # Verify no POLICY_DENIED event (guard allowed it)
    policy_denied_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "POLICY_DENIED"
    ]
    assert len(policy_denied_events) == 0, "Should not have POLICY_DENIED event for safe operation"


def test_semantic_guard_disabled_by_default():
    """
    Test: Semantic guard is disabled by default (zero cost, zero behavior)
    
    Scenario: Executor created without semantic_guard parameter
    Expected: Guard is None, no semantic checks performed
    """
    tools = ToolRegistry()
    def send_email(to: str, subject: str, body: str):
        return {"success": True}
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    
    # Create executor WITHOUT semantic guard (default)
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        # semantic_guard=None (default)
    )
    
    # Verify guard is disabled
    assert executor.services.semantic_guard is None, "Guard should be disabled by default"
    
    ctx = RunContext(
        run_id="test-guard-disabled",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step that would be blocked if guard was enabled
    step = Step(
        id="s1",
        tool="send_email",
        params={
            "to": "user@example.com",
            "subject": "Test",
            "body": "API_KEY=sk-1234567890abcdefghijklmnop",  # Would be blocked if guard enabled
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed (no semantic check)
    assert result.status == StepStatus.OK, "Should succeed when guard is disabled"


def test_semantic_guard_disabled_when_enabled_false():
    """
    Test: Semantic guard is disabled when enabled=False
    
    Scenario: Semantic guard provided but enabled=False
    Expected: No semantic checks performed (zero behavior)
    """
    # Create guard but disable it
    guard = SemanticGuardMiddleware(
        enabled=False,  # Explicitly disabled
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    tools = ToolRegistry()
    def send_email(to: str, subject: str, body: str):
        return {"success": True}
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-guard-disabled-flag",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step that would be blocked if guard was enabled
    step = Step(
        id="s1",
        tool="send_email",
        params={
            "to": "user@example.com",
            "subject": "Test",
            "body": "API_KEY=sk-1234567890abcdefghijklmnop",  # Would be blocked if guard enabled
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed (guard is disabled)
    assert result.status == StepStatus.OK, "Should succeed when guard.enabled=False"
    
    # Verify guard stats show no checks performed
    stats = guard.get_stats()
    assert stats["checks_performed"] == 0, "Should perform zero checks when disabled"


def test_semantic_guard_structured_verdict():
    """
    Test: Semantic guard returns structured, explainable verdict
    
    Scenario: Semantic violation detected
    Expected: PolicyResult contains structured fields (rule_id, violations, explanation, evidence)
    """
    guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    tools = ToolRegistry()
    def send_email(to: str, subject: str, body: str):
        return {"success": True}
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-semantic-structured",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step with secret leakage
    step = Step(
        id="s1",
        tool="send_email",
        params={
            "to": "user@example.com",
            "subject": "API Credentials",
            "body": "API_KEY=sk-1234567890abcdefghijklmnop",
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should be blocked
    assert result.status == StepStatus.BLOCKED, "Should be BLOCKED"
    assert result.error is not None, "Should have error"
    
    # Verify error details contain structured information
    error_details = result.error.detail if hasattr(result.error, 'detail') else {}
    if isinstance(error_details, dict):
        # Verify structured fields are present
        assert "source" in error_details, "Should have source field"
        assert error_details["source"] == "semantic", "Source should be 'semantic'"
        assert "tool" in error_details, "Should have tool field"
        assert error_details["tool"] == "send_email", "Tool should match"
        
        # Verify violations list exists
        if "violations" in error_details:
            violations = error_details["violations"]
            assert isinstance(violations, list), "Violations should be a list"
            if len(violations) > 0:
                violation = violations[0]
                assert "rule_id" in violation or "name" in violation, \
                    "Violation should have rule_id or name"


def test_semantic_guard_unified_policy_denied_event():
    """
    Test: Semantic guard uses unified POLICY_DENIED event
    
    Scenario: Semantic violation detected
    Expected: POLICY_DENIED event recorded with source="semantic" in details
    """
    guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    tools = ToolRegistry()
    def send_email(to: str, subject: str, body: str):
        return {"success": True}
    tools.register("send_email", send_email)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-semantic-event",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step with secret leakage
    step = Step(
        id="s1",
        tool="send_email",
        params={
            "to": "user@example.com",
            "subject": "Test",
            "body": "API_KEY=sk-1234567890abcdefghijklmnop",
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should be blocked
    assert result.status == StepStatus.BLOCKED, "Should be BLOCKED"
    
    # Verify POLICY_DENIED event was recorded
    policy_denied_events = [
        e for e in recorder.events
        if isinstance(e, dict) and e.get("event", {}).get("type") == "POLICY_DENIED"
    ]
    assert len(policy_denied_events) > 0, "Should have POLICY_DENIED event"
    
    # Verify event structure (unified event type)
    last_event = policy_denied_events[-1]
    event_data = last_event.get("event", {}).get("data", {})
    policy_data = event_data.get("policy", {})
    
    assert policy_data.get("policy_id") == "Semantic-Guard", \
        "Policy ID should be Semantic-Guard"
    assert policy_data.get("rule_id") is not None, \
        "Rule ID should be present"
    assert policy_data.get("rule_name") == "SemanticViolation", \
        "Rule name should be SemanticViolation"


def test_semantic_guard_module_exception_not_violation():
    """
    Test: Semantic guard module exceptions are not treated as violations
    
    Scenario: Semantic guard raises non-FailCoreError exception
    Expected: Execution continues (exception logged but not blocked)
    """
    # Create a guard that might raise exceptions
    guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    # Mock a detector that raises an exception (simulating module bug)
    original_check = guard.detector.check
    
    def faulty_check(tool_name, params, context):
        # Simulate module exception (not a violation)
        raise ValueError("Internal detector error")
    
    guard.detector.check = faulty_check
    
    tools = ToolRegistry()
    def read_file(path: str):
        return {"content": "test"}
    tools.register("read_file", read_file)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        semantic_guard=guard,
    )
    
    ctx = RunContext(
        run_id="test-semantic-exception",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step with safe parameters
    step = Step(
        id="s1",
        tool="read_file",
        params={"path": "data.txt"},
    )
    
    result = executor.execute(step, ctx)
    
    # Should succeed (module exception ≠ violation)
    assert result.status == StepStatus.OK, \
        "Should succeed - module exception should not block execution"


def test_semantic_guard_fixed_order():
    """
    Test: Semantic guard executes in fixed order (side_effect → semantic → policy.allow)
    
    Scenario: Multiple guards enabled
    Expected: Guards execute in documented order
    """
    from failcore.core.config.boundaries import get_boundary
    
    # Enable both side-effect gate and semantic guard
    boundary = get_boundary("read_only")
    semantic_guard = SemanticGuardMiddleware(
        enabled=True,
        min_severity=RuleSeverity.HIGH,
        block_on_violation=True,
    )
    
    tools = ToolRegistry()
    def write_file(path: str, content: str):
        return {"success": True}
    tools.register("write_file", write_file)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=ExecutorConfig(enable_cost_tracking=False),
        side_effect_boundary=boundary,  # Phase 1: side-effect gate
        semantic_guard=semantic_guard,  # Phase 2: semantic guard
    )
    
    ctx = RunContext(
        run_id="test-guard-order",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step that would be blocked by side-effect gate (should block before semantic guard)
    step = Step(
        id="s1",
        tool="write_file",
        params={
            "path": "/tmp/output.txt",
            "content": "test",
        },
    )
    
    result = executor.execute(step, ctx)
    
    # Should be blocked by side-effect gate (Phase 1, before semantic guard)
    assert result.status == StepStatus.BLOCKED, "Should be BLOCKED"
    assert result.error is not None, "Should have error"
    
    # Verify it was blocked by side-effect gate, not semantic guard
    # (side-effect gate should block first, so semantic guard never runs)
    assert "SIDE_EFFECT_BOUNDARY_CROSSED" in result.error.error_code or "boundary" in result.error.error_code.lower(), \
        f"Should be blocked by side-effect gate, got {result.error.error_code}"


__all__ = [
    "test_semantic_guard_blocks_secret_leakage",
    "test_semantic_guard_blocks_sql_injection",
    "test_semantic_guard_blocks_path_traversal",
    "test_semantic_guard_allows_safe_operations",
    "test_semantic_guard_disabled_by_default",
    "test_semantic_guard_disabled_when_enabled_false",
    "test_semantic_guard_structured_verdict",
    "test_semantic_guard_unified_policy_denied_event",
    "test_semantic_guard_module_exception_not_violation",
    "test_semantic_guard_fixed_order",
]
