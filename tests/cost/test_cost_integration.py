"""
Test Cost Integration - Budget Enforcement in Executor

Tests for:
- Cost tracking in STEP_END events (incremental + cumulative)
- Budget pre-check before execution
- BLOCKED status when budget exceeded
- Trace as single source of truth
"""

from datetime import datetime, timezone

from failcore.core.executor import Executor, ExecutorConfig
from failcore.core.tools import ToolRegistry
from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.trace import TraceRecorder
from failcore.core.cost import CostGuardian, CostEstimator


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


def test_cost_integration_normal_execution():
    """Test: Normal execution with cost tracking"""
    # Create Cost Guardian
    guardian = CostGuardian(
        max_cost_usd=1.0,
        max_tokens=10000,
        max_usd_per_minute=0.5,
    )
    
    # Create Cost Estimator
    estimator = CostEstimator()
    
    # Create simple tools
    def mock_llm_tool(prompt: str) -> str:
        return f"Response to: {prompt[:50]}..."
    
    def mock_cheap_tool(query: str) -> str:
        return f"Result for: {query}"
    
    tools = ToolRegistry()
    tools.register("llm_generate", mock_llm_tool)
    tools.register("search", mock_cheap_tool)
    
    recorder = MockTraceRecorder()
    
    # Create Executor
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test-run-001",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/sandbox",
        cwd="/tmp/sandbox",
    )
    
    # Execute a cheap tool (should succeed)
    step1 = Step(
        id="s1",
        tool="search",
        params={"query": "test query"},
        meta={"cost_usd": 0.0001},
    )
    
    result1 = executor.execute(step1, ctx)
    
    assert result1.status == StepStatus.OK, "Step 1 should succeed"
    
    # Check trace for cost information
    step_end_events = [e for e in recorder.events if e["event"]["type"] == "STEP_END"]
    assert len(step_end_events) > 0, "Should have STEP_END event"
    
    last_event = step_end_events[-1]
    metrics = last_event["event"]["data"].get("metrics")
    assert metrics is not None, "Should have metrics"
    assert "cost" in metrics, "Should have cost metrics"
    
    cost = metrics["cost"]
    assert "incremental" in cost, "Should have incremental cost"
    assert "cumulative" in cost, "Should have cumulative cost"
    assert cost["incremental"]["cost_usd"] >= 0
    assert cost["cumulative"]["cost_usd"] >= 0


def test_cost_integration_budget_exceeded():
    """Test: Budget exceeded should block execution"""
    guardian = CostGuardian(
        max_cost_usd=1.0,
        max_tokens=10000,
    )
    
    estimator = CostEstimator()
    
    def mock_llm_tool(prompt: str) -> str:
        return f"Response to: {prompt[:50]}..."
    
    tools = ToolRegistry()
    tools.register("llm_generate", mock_llm_tool)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test-run-002",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/sandbox",
        cwd="/tmp/sandbox",
    )
    
    # Create expensive step (should be blocked)
    step2 = Step(
        id="s2",
        tool="llm_generate",
        params={"prompt": "Generate a very long document" * 100},
        meta={
            "model": "gpt-4",
            "cost_usd": 2.0,  # Exceeds budget!
        },
    )
    
    result2 = executor.execute(step2, ctx)
    
    # Should be blocked
    assert result2.status == StepStatus.BLOCKED, "Step 2 should be blocked"
    assert result2.error is not None, "Should have error"
    assert "BUDGET" in result2.error.error_code or "ECONOMIC" in result2.error.error_code, \
        f"Error code should mention budget, got {result2.error.error_code}"
    
    # Check trace for BLOCKED status
    step_end_events = [e for e in recorder.events if e["event"]["type"] == "STEP_END"]
    assert len(step_end_events) > 0, "Should have STEP_END event"
    
    last_event = step_end_events[-1]
    event_data = last_event["event"]["data"]
    assert event_data["result"]["status"].upper() == "BLOCKED", "Trace should show BLOCKED status"
    
    # Even when blocked, should have cost information (estimated)
    if "metrics" in event_data:
        assert "cost" in event_data["metrics"], "Should have cost metrics even when blocked"


def test_cost_integration_guardian_status():
    """Test: CostGuardian status tracking"""
    guardian = CostGuardian(
        max_cost_usd=1.0,
        max_tokens=10000,
    )
    
    estimator = CostEstimator()
    
    def mock_tool(x: str) -> str:
        return f"Result: {x}"
    
    tools = ToolRegistry()
    tools.register("test_tool", mock_tool)
    
    recorder = MockTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test-run-003",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/sandbox",
        cwd="/tmp/sandbox",
    )
    
    # Execute a step
    step = Step(
        id="s1",
        tool="test_tool",
        params={"x": "test"},
        meta={"cost_usd": 0.1},
    )
    
    executor.execute(step, ctx)
    
    # Check guardian status
    status = guardian.get_status()
    assert "operations_checked" in status
    assert status["operations_checked"] >= 1
    
    # Check executor run cost
    run_cost = executor.get_run_cost(ctx.run_id)
    assert run_cost["cost_usd"] >= 0
    assert run_cost["tokens"] >= 0
    assert run_cost["api_calls"] >= 0


def test_trace_as_source_of_truth():
    """Test: Trace contains complete cost information"""
    # Simulate trace data
    trace_data = [
        {
            "schema": "failcore.trace.v0.1.2",
            "seq": 1,
            "event": {"type": "RUN_START"},
        },
        {
            "schema": "failcore.trace.v0.1.2",
            "seq": 2,
            "event": {
                "type": "STEP_END",
                "step": {"id": "s1", "tool": "search"},
                "data": {
                    "result": {"status": "OK"},
                    "metrics": {
                        "cost": {
                            "incremental": {"cost_usd": 0.001, "tokens": 100},
                            "cumulative": {"cost_usd": 0.001, "tokens": 100},
                        }
                    }
                }
            }
        },
        {
            "schema": "failcore.trace.v0.1.2",
            "seq": 3,
            "event": {
                "type": "STEP_END",
                "step": {"id": "s2", "tool": "llm_generate"},
                "data": {
                    "result": {"status": "OK"},
                    "metrics": {
                        "cost": {
                            "incremental": {"cost_usd": 0.500, "tokens": 5000},
                            "cumulative": {"cost_usd": 0.501, "tokens": 5100},
                        }
                    }
                }
            }
        },
    ]
    
    # Reconstruct cost curve from trace
    cumulative_cost = 0.0
    for event in trace_data:
        if event["event"]["type"] == "STEP_END":
            data = event["event"]["data"]
            metrics = data.get("metrics", {})
            
            if "cost" in metrics:
                cost = metrics["cost"]
                incr = cost["incremental"]["cost_usd"]
                cumul = cost["cumulative"]["cost_usd"]
                
                assert incr >= 0, "Incremental cost should be non-negative"
                assert cumul >= cumulative_cost, "Cumulative should be increasing"
                cumulative_cost = cumul
    
    assert cumulative_cost > 0, "Should have cumulative cost"
