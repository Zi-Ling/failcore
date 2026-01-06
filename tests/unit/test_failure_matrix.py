# tests/unit/test_failure_matrix.py
from __future__ import annotations

from failcore.core.executor.executor import Executor, ExecutorConfig
from failcore.core.types.step.step import Step, RunContext
from failcore.core.trace.recorder import NullTraceRecorder
from failcore.core.tools.registry import ToolRegistry
from failcore.core.executor.executor import Policy


class DenyAllPolicy(Policy):
    def allow(self, step: Step, ctx: RunContext):
        return False, "Denied for test"


def make_executor(*, tools: ToolRegistry, policy: Policy | None = None) -> Executor:
    # 用 NullTraceRecorder 避免写文件
    return Executor(
        tools=tools,
        recorder=NullTraceRecorder(),
        policy=policy,
        config=ExecutorConfig(include_stack=False),
    )


def test_tool_not_found():
    tools = ToolRegistry()  # 不注册 divide
    ex = make_executor(tools=tools)

    ctx = RunContext()
    step = Step(id="s1", tool="divide", params={"a": 6, "b": 2})

    result = ex.execute(step, ctx)

    assert result.status.value == "fail"
    assert result.error is not None
    assert result.error.error_code == "TOOL_NOT_FOUND"
    assert "divide" in result.error.message


def test_tool_raised():
    tools = ToolRegistry()
    tools.register("divide", lambda a, b: a / b)

    ex = make_executor(tools=tools)

    ctx = RunContext()
    step = Step(id="s1", tool="divide", params={"a": 1, "b": 0})  # ZeroDivisionError

    result = ex.execute(step, ctx)

    assert result.status.value == "fail"
    assert result.error is not None
    assert result.error.error_code == "TOOL_RAISED"
    assert "division by zero" in result.error.message.lower() or "zerodivisionerror" in result.error.message.lower()


def test_policy_deny():
    tools = ToolRegistry()
    tools.register("divide", lambda a, b: a / b)

    ex = make_executor(tools=tools, policy=DenyAllPolicy())

    ctx = RunContext()
    step = Step(id="s1", tool="divide", params={"a": 6, "b": 2})

    result = ex.execute(step, ctx)

    # v0.1.2: Policy interception returns BLOCKED, not FAIL
    # BLOCKED = policy/validation phase interception (before execution)
    # FAIL = execution phase error (during tool execution)
    assert result.status.value == "blocked"
    assert result.error is not None
    assert result.error.error_code == "POLICY_DENY"
    assert "Denied" in result.error.message
