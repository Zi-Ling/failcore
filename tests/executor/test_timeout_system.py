# tests/executor/test_timeout_system.py
"""
Timeout system tests - validate timeout enforcement behavior

Tests cover:
1. Timeout returns correct StepStatus.TIMEOUT and event
2. Timeout kills process group (not entire session)
3. Timeout does NOT call cleanup() (avoids killing other steps)
"""

import os
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.executor import Executor, ExecutorConfig
from failcore.core.tools import ToolRegistry, ToolSpec, ToolMetadata


class InMemoryTraceRecorder:
    """
    Minimal trace recorder for testing with unified event structure
    
    统一事件结构：所有事件都标准化为 {"event": {...}} 格式
    这样测试断言更稳定，不依赖具体序列化实现
    """
    def __init__(self):
        self.events = []
        self._seq = 0
    
    def record(self, event):
        """
        Record event with unified structure
        
        统一处理：所有事件都转换为 {"event": {...}} 格式
        """
        if isinstance(event, dict):
            # 如果已经是标准格式 {"event": {...}}，直接使用
            if "event" in event:
                self.events.append(event)
            else:
                # 否则包装为标准格式
                self.events.append({"event": event})
        elif hasattr(event, "to_dict"):
            # TraceEvent 对象，转换为标准格式
            event_dict = event.to_dict()
            # 确保是 {"event": {...}} 格式
            if "event" in event_dict:
                self.events.append(event_dict)
            else:
                self.events.append({"event": event_dict})
        else:
            # 未知格式，包装为标准格式
            self.events.append({"event": {"raw": str(event)}})
    
    def next_seq(self):
        self._seq += 1
        return self._seq
    
    def get_events_by_type(self, event_type: str):
        """
        Get all events of a specific type
        
        统一结构：所有事件都是 {"event": {"type": ...}} 格式
        """
        result = []
        for event in self.events:
            # 统一结构：event["event"]["type"]
            event_obj = event.get("event", {}) if isinstance(event, dict) else {}
            if isinstance(event_obj, dict) and event_obj.get("type") == event_type:
                result.append(event)
        return result


def tool_sleepy(seconds: float) -> dict:
    """Tool that sleeps for specified seconds"""
    time.sleep(seconds)
    return {"slept": seconds}


def tool_blocking_event() -> dict:
    """
    Tool that blocks indefinitely using threading.Event
    
    用于超时测试：更可控，不会受系统调度影响
    """
    import threading
    event = threading.Event()
    event.wait()  # 永远阻塞，直到超时被切断
    return {"blocked": True}


def build_executor_with_timeout(
    sandbox_root: str,
    default_timeout: float = 0.1,
    max_timeout: float = 3600.0,
    enable_timeout: bool = True,
) -> tuple[Executor, ToolRegistry, InMemoryTraceRecorder]:
    """
    Build executor with timeout configuration
    
    Args:
        sandbox_root: Sandbox root directory (must exist, lifecycle managed by caller)
        default_timeout: Default timeout in seconds
        max_timeout: Maximum timeout in seconds
        enable_timeout: Whether to enable timeout enforcement
        
    Returns:
        Tuple of (executor, tools, recorder)
    """
    tools = ToolRegistry(sandbox_root=sandbox_root)
    recorder = InMemoryTraceRecorder()
    
    config = ExecutorConfig(
        default_timeout=default_timeout,
        max_timeout=max_timeout,
        enable_timeout_enforcement=enable_timeout,
    )
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        config=config,
    )
    
    return executor, tools, recorder


def make_ctx(sandbox_root: str, run_id: str) -> RunContext:
    """Create RunContext"""
    return RunContext(
        run_id=run_id,
        created_at=time.time(),
        sandbox_root=sandbox_root,
        cwd=sandbox_root,
    )


# ============================================================
# Test Case 1: Timeout returns StepStatus.TIMEOUT and event
# ============================================================

def test_timeout_returns_stepstatus_timeout_and_event():
    """
    用例1：阻塞工具触发超时，返回 StepStatus.TIMEOUT，并写入 STEP_TIMEOUT 事件
    
    验收标准：
    - result.status == StepStatus.TIMEOUT
    - result.error.error_code == "STEP_TIMEOUT"
    - trace 里有 STEP_TIMEOUT 事件
    """
    with tempfile.TemporaryDirectory() as td:
        sandbox = os.path.join(td, "sandbox")
        os.makedirs(sandbox, exist_ok=True)
        
        executor, tools, recorder = build_executor_with_timeout(
            sandbox_root=sandbox,
            default_timeout=0.1,  # 100ms timeout
        )
        
        # Register blocking tool (更可控，不会受系统调度影响)
        tools.register_tool(
            ToolSpec(
                name="blocking",
                fn=tool_blocking_event,
                tool_metadata=ToolMetadata(),
            )
        )
        
        ctx = make_ctx(sandbox, "timeout-test-1")
        
        # Execute step that will timeout
        step = Step(id="s1", tool="blocking", params={})
        result = executor.execute(step, ctx)
        
        # Assert 1: Status is TIMEOUT
        assert result.status == StepStatus.TIMEOUT, \
            f"Expected TIMEOUT status, got {result.status}"
        
        # Assert 2: Error code is STEP_TIMEOUT
        assert result.error is not None, "Result should have error"
        assert result.error.error_code == "STEP_TIMEOUT", \
            f"Expected error code 'STEP_TIMEOUT', got '{result.error.error_code}'"
        
        # Assert 3: Error detail contains timeout_seconds (使用近似断言)
        assert "timeout_seconds" in result.error.detail, \
            "Error detail should contain timeout_seconds"
        timeout_val = result.error.detail["timeout_seconds"]
        assert timeout_val == pytest.approx(0.1, rel=1e-2), \
            f"Expected timeout_seconds≈0.1, got {timeout_val}"
        
        # Assert 4: Trace contains STEP_TIMEOUT event
        timeout_events = recorder.get_events_by_type("STEP_TIMEOUT")
        assert len(timeout_events) > 0, \
            "Trace should contain at least one STEP_TIMEOUT event"
        
        # Assert 5: Event data contains timeout_seconds (统一结构：event["event"]["data"])
        event_data = timeout_events[0].get("event", {}).get("data", {})
        assert "timeout_seconds" in event_data, \
            "STEP_TIMEOUT event should contain timeout_seconds"
        event_timeout = event_data["timeout_seconds"]
        assert event_timeout == pytest.approx(0.1, rel=1e-2), \
            f"Expected timeout_seconds≈0.1 in event, got {event_timeout}"


# ============================================================
# Test Case 3: Timeout kills process group
# ============================================================

def test_timeout_kills_process_group_unit():
    """
    纯单元测试：强制注入 pgid，验证 kill_process_group 被调用且参数正确
    
    验收标准：
    - kill_process_group 被调用一次
    - 调用参数 pgid 正确
    - 不依赖 executor.services 的存在性
    """
    with tempfile.TemporaryDirectory() as td:
        sandbox = os.path.join(td, "sandbox")
        os.makedirs(sandbox, exist_ok=True)
        
        executor, tools, recorder = build_executor_with_timeout(
            sandbox_root=sandbox,
            default_timeout=0.1,
        )
        
        # Register blocking tool
        tools.register_tool(
            ToolSpec(
                name="blocking",
                fn=tool_blocking_event,
                tool_metadata=ToolMetadata(),
            )
        )
        
        # 强制注入 PGID（不依赖 executor.services 的存在性）
        fake_pgid = 12345
        process_registry = executor.services.process_registry
        assert process_registry is not None, "Process registry should exist"
        process_registry.set_process_group(fake_pgid)
        
        # 修复点3：patch 调用方的命名空间
        # dispatch.py 在 _handle_timeout 函数内部 import kill_process_group
        # 由于是函数内部 import，需要确保 patch 在 import 之前生效
        # 方法：patch 模块级别的函数，函数内部 import 会使用已 patch 的版本
        # 使用 patch.object 更可靠，因为它直接操作模块对象
        import failcore.utils.process as process_module
        
        with patch.object(process_module, 'kill_process_group') as mock_kill:
            # Mock successful kill
            mock_kill.return_value = (True, None)
            
            ctx = make_ctx(sandbox, "timeout-test-3-unit")
            
            # Execute step that will timeout
            step = Step(id="s1", tool="blocking", params={})
            result = executor.execute(step, ctx)
            
            # Assert 1: Status is TIMEOUT
            assert result.status == StepStatus.TIMEOUT
            
            # Assert 2: kill_process_group was called exactly once
            assert mock_kill.call_count == 1, \
                f"kill_process_group should be called exactly once, got {mock_kill.call_count}"
            
            # Assert 3: Called with correct PGID
            call = mock_kill.call_args_list[0]
            args = call[0] if call and len(call) > 0 else ()
            kwargs = call[1] if call and len(call) > 1 else {}
            
            # kill_process_group uses keyword arguments: kill_process_group(pgid=pgid, ...)
            if kwargs and 'pgid' in kwargs:
                actual_pgid = kwargs['pgid']
                assert actual_pgid == fake_pgid, \
                    f"Expected kill_process_group called with pgid={fake_pgid}, got {actual_pgid}"
            elif args and len(args) > 0:
                actual_pgid = args[0]
                assert actual_pgid == fake_pgid, \
                    f"Expected kill_process_group called with pgid={fake_pgid}, got {actual_pgid}"
            else:
                pytest.fail("kill_process_group called but unable to verify pgid parameter")


def test_timeout_process_group_in_event():
    """
    集成测试：验证在真实执行链路里 process_group 字段被写入事件
    
    验收标准：
    - trace 的 STEP_TIMEOUT data 里包含 process_group 信息
    - process_group.pgid、killed、kill_error 字段存在
    """
    with tempfile.TemporaryDirectory() as td:
        sandbox = os.path.join(td, "sandbox")
        os.makedirs(sandbox, exist_ok=True)
        
        executor, tools, recorder = build_executor_with_timeout(
            sandbox_root=sandbox,
            default_timeout=0.1,
        )
        
        # Register blocking tool
        tools.register_tool(
            ToolSpec(
                name="blocking",
                fn=tool_blocking_event,
                tool_metadata=ToolMetadata(),
            )
        )
        
        # Set PGID
        fake_pgid = 12345
        process_registry = executor.services.process_registry
        if process_registry:
            process_registry.set_process_group(fake_pgid)
        
        ctx = make_ctx(sandbox, "timeout-test-3-integration")
        
        # Execute step that will timeout
        step = Step(id="s1", tool="blocking", params={})
        result = executor.execute(step, ctx)
        
        # Assert 1: Status is TIMEOUT
        assert result.status == StepStatus.TIMEOUT
        
        # Assert 2: Trace event contains process_group info
        timeout_events = recorder.get_events_by_type("STEP_TIMEOUT")
        assert len(timeout_events) > 0, "Should have STEP_TIMEOUT event"
        
        # 统一结构：event["event"]["data"]
        event_data = timeout_events[0].get("event", {}).get("data", {})
        assert "process_group" in event_data, \
            "STEP_TIMEOUT event should contain process_group data"
        
        pg_data = event_data["process_group"]
        assert "pgid" in pg_data, "process_group should have pgid"
        assert "killed" in pg_data, "process_group should have killed flag"
        assert "kill_error" in pg_data, "process_group should have kill_error field"
        
        # If PGID was set, verify it matches
        if process_registry and process_registry.get_process_group():
            assert pg_data["pgid"] == fake_pgid, \
                f"Expected pgid={fake_pgid} in event, got {pg_data['pgid']}"


# ============================================================
# Test Case 4: Timeout does NOT call cleanup
# ============================================================

def test_timeout_does_not_call_cleanup():
    """
    用例4：保证不误杀其他 step，不会调用 session cleanup
    
    验收标准：
    - ProcessRegistry.cleanup() 不会被调用
    - 如果被调用会 raise，测试应通过（说明没调用）
    """
    with tempfile.TemporaryDirectory() as td:
        sandbox = os.path.join(td, "sandbox")
        os.makedirs(sandbox, exist_ok=True)
        
        executor, tools, recorder = build_executor_with_timeout(
            sandbox_root=sandbox,
            default_timeout=0.1,
        )
        
        # Register blocking tool
        tools.register_tool(
            ToolSpec(
                name="blocking",
                fn=tool_blocking_event,
                tool_metadata=ToolMetadata(),
            )
        )
        
        # 修复点6：使用 patch.object 替代直接 monkeypatch
        process_registry = executor.services.process_registry
        assert process_registry is not None, "Process registry should exist"
        
        # 使用 patch.object：如果 cleanup 被调用，会 raise AssertionError
        with patch.object(
            process_registry,
            "cleanup",
            side_effect=AssertionError("cleanup() should NOT be called on timeout!")
        ):
            ctx = make_ctx(sandbox, "timeout-test-4")
            
            # Execute step that will timeout
            step = Step(id="s1", tool="blocking", params={})
            result = executor.execute(step, ctx)
            
            # Assert 1: Status is TIMEOUT (timeout occurred)
            assert result.status == StepStatus.TIMEOUT
            
            # Assert 2: 如果 cleanup 被调用，patch.object 的 side_effect 会 raise
            # 测试能到这里说明 cleanup 没有被调用（测试通过）


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
