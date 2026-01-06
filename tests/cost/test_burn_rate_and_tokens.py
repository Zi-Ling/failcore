"""
测试 Burn Rate 和 Token 统计

完整验证:
1. Burn rate 限制 (滑动窗口)
2. Token 统计 (从工具返回值提取)
"""

from datetime import datetime, timezone

from failcore.core.executor import Executor, ExecutorConfig
from failcore.core.tools import ToolRegistry
from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.trace import TraceRecorder
from failcore.core.cost import CostGuardian, CostEstimator, UsageExtractor


class TestTraceRecorder(TraceRecorder):
    """测试用 Trace Recorder"""
    def __init__(self):
        self._seq = 0
        self.events = []
    
    def next_seq(self):
        self._seq += 1
        return self._seq
    
    def record(self, event):
        self.events.append(event.to_dict())


def test_burn_rate_enforcement():
    """测试1: Burn rate 限制"""
    print("\n" + "=" * 70)
    print("测试 1: Burn Rate 限制（1分钟内连续高成本操作）")
    print("=" * 70)
    
    # 设置非常严格的 burn rate 限制
    guardian = CostGuardian(
        max_cost_usd=100.0,  # 总预算很大
        max_usd_per_minute=0.5,  # 但每分钟只能花 $0.50
    )
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("expensive_tool", lambda x: f"expensive result: {x}")
    
    recorder = TestTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test-burn-rate",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Step 1: $0.3 (应该成功)
    step1 = Step(
        id="s1",
        tool="expensive_tool",
        params={"x": "task1"},
        meta={"cost_usd": 0.3},
    )
    result1 = executor.execute(step1, ctx)
    print(f"Step 1 ($0.30): status={result1.status}")
    assert result1.status == StepStatus.OK, "Step 1 should succeed"
    
    # Step 2: $0.3 (累计 $0.6，超过 $0.5/min，应该被拦截)
    step2 = Step(
        id="s2",
        tool="expensive_tool",
        params={"x": "task2"},
        meta={"cost_usd": 0.3},
    )
    result2 = executor.execute(step2, ctx)
    print(f"Step 2 ($0.30): status={result2.status}, error={result2.error.error_code if result2.error else None}")
    
    # 验证被 burn rate 拦截
    assert result2.status == StepStatus.BLOCKED, f"Step 2 should be BLOCKED by burn rate, got {result2.status}"
    # CostPrecheckStage maps "BURN_RATE_EXCEEDED" to codes.ECONOMIC_BURN_RATE_EXCEEDED
    assert result2.error.error_code == "ECONOMIC_BURN_RATE_EXCEEDED", \
        f"Should be ECONOMIC_BURN_RATE_EXCEEDED, got {result2.error.error_code}"
    
    # 检查错误详情包含 burn rate 相关信息
    assert "budget_reason" in result2.error.detail, "Error detail should have budget_reason"
    assert "burn rate" in result2.error.detail["budget_reason"].lower(), "Should mention burn rate"
    
    print("✅ Burn rate 限制正确触发!")
    
    # 验证 trace 中的事件
    step_ends = [e for e in recorder.events if e["event"]["type"] == "STEP_END"]
    assert len(step_ends) == 2, "Should have 2 STEP_END events"
    
    blocked_event = step_ends[1]
    assert blocked_event["event"]["data"]["result"]["status"].upper() == "BLOCKED"
    # CostPrecheckStage maps to canonical error code ECONOMIC_BURN_RATE_EXCEEDED
    assert blocked_event["event"]["data"]["result"]["error"]["code"] == "ECONOMIC_BURN_RATE_EXCEEDED"
    
    # BLOCKED 步骤应该有 metrics
    assert "metrics" in blocked_event["event"]["data"], "BLOCKED step must have metrics"
    
    print("✅ Trace 验证通过!")
    return True


def test_token_extraction():
    """测试2: 从工具返回值提取 Token 统计"""
    print("\n" + "=" * 70)
    print("测试 2: Token 统计提取（从工具返回值）")
    print("=" * 70)
    
    guardian = CostGuardian(max_cost_usd=10.0)
    estimator = CostEstimator()
    
    # 模拟 LLM 工具（返回带 usage 的结果）
    def mock_llm_tool(prompt: str):
        """模拟 LLM 工具，返回带 usage 的结果"""
        return {
            "result": f"Generated text for: {prompt}",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "cost_usd": 0.015,
                "model": "gpt-4",
                "provider": "openai",
            }
        }
    
    # 模拟 OpenAI 风格的返回（使用 prompt_tokens/completion_tokens）
    class OpenAIStyleResponse:
        def __init__(self):
            self.result = "AI generated response"
            self.usage = type('obj', (object,), {
                'prompt_tokens': 200,
                'completion_tokens': 100,
                'total_tokens': 300,
            })()
    
    def mock_openai_tool(prompt: str):
        return OpenAIStyleResponse()
    
    tools = ToolRegistry()
    tools.register("llm_generate", mock_llm_tool)
    tools.register("openai_chat", mock_openai_tool)
    
    recorder = TestTraceRecorder()
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test-token-extraction",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # Test Case 1: Dict with usage
    print("\nCase 1: Dict 格式（标准 usage）")
    step1 = Step(
        id="s1",
        tool="llm_generate",
        params={"prompt": "Hello"},
    )
    result1 = executor.execute(step1, ctx)
    print(f"  Status: {result1.status}")
    
    # 验证 trace 中的 tokens
    step_ends = [e for e in recorder.events if e["event"]["type"] == "STEP_END"]
    last_event = step_ends[-1]
    
    metrics = last_event["event"]["data"].get("metrics", {})
    cost = metrics.get("cost", {})
    incremental = cost.get("incremental", {})
    
    print(f"  Input tokens: {incremental.get('input_tokens')}")
    print(f"  Output tokens: {incremental.get('output_tokens')}")
    print(f"  Total tokens: {incremental.get('tokens')}")
    print(f"  Cost: ${incremental.get('cost_usd'):.6f}")
    print(f"  Estimated: {incremental.get('estimated')}")
    
    # 断言
    assert incremental.get("tokens") == 150, "Should extract 150 tokens"
    assert incremental.get("input_tokens") == 100, "Should extract 100 input tokens"
    assert incremental.get("output_tokens") == 50, "Should extract 50 output tokens"
    assert abs(incremental.get("cost_usd", 0) - 0.015) < 0.001, "Should extract $0.015 cost"
    assert incremental.get("estimated") == False, "Should mark as non-estimated (real usage)"
    # build_cost_metrics uses pricing_ref format: "provider:model"
    assert incremental.get("pricing_ref") == "openai:gpt-4", f"Should extract pricing_ref, got {incremental.get('pricing_ref')}"
    
    print("  ✅ Dict 格式提取正确!")
    
    # Test Case 2: OpenAI-style object
    print("\nCase 2: OpenAI 格式（object with .usage）")
    step2 = Step(
        id="s2",
        tool="openai_chat",
        params={"prompt": "Test"},
    )
    result2 = executor.execute(step2, ctx)
    
    step_ends = [e for e in recorder.events if e["event"]["type"] == "STEP_END"]
    last_event = step_ends[-1]
    
    metrics = last_event["event"]["data"].get("metrics", {})
    cost = metrics.get("cost", {})
    incremental = cost.get("incremental", {})
    
    print(f"  Input tokens: {incremental.get('input_tokens')}")
    print(f"  Output tokens: {incremental.get('output_tokens')}")
    print(f"  Total tokens: {incremental.get('tokens')}")
    print(f"  Estimated: {incremental.get('estimated')}")
    
    # 断言
    assert incremental.get("tokens") == 300, "Should extract 300 tokens"
    assert incremental.get("input_tokens") == 200, "Should extract 200 input tokens"
    assert incremental.get("output_tokens") == 100, "Should extract 100 output tokens"
    assert incremental.get("estimated") == False, "Should mark as non-estimated"
    
    print("  ✅ OpenAI 格式提取正确!")
    
    print("\n✅ Token 统计功能完全正常!")
    return True


def test_usage_extractor_directly():
    """测试3: 直接测试 UsageExtractor"""
    print("\n" + "=" * 70)
    print("测试 3: UsageExtractor 单元测试")
    print("=" * 70)
    
    # Case 1: Dict format
    output1 = {
        "result": "text",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.001,
        }
    }
    
    usage1 = UsageExtractor.extract(output1, "run1", "s1", "tool1")
    assert usage1 is not None, "Should extract usage from dict"
    assert usage1.input_tokens == 10
    assert usage1.output_tokens == 5
    assert usage1.total_tokens == 15
    assert usage1.estimated == False
    print("  ✅ Dict 格式")
    
    # Case 2: Object with .usage attribute
    class MockResponse:
        def __init__(self):
            self.result = "test"
            self.usage = {"input_tokens": 20, "output_tokens": 10}
    
    output2 = MockResponse()
    usage2 = UsageExtractor.extract(output2, "run1", "s2", "tool2")
    assert usage2 is not None
    assert usage2.input_tokens == 20
    assert usage2.output_tokens == 10
    print("  ✅ Object 格式")
    
    # Case 3: No usage info
    output3 = "plain string result"
    usage3 = UsageExtractor.extract(output3, "run1", "s3", "tool3")
    assert usage3 is None, "Should return None for plain results"
    print("  ✅ 无 usage 时返回 None")
    
    print("\n✅ UsageExtractor 单元测试通过!")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("Burn Rate 和 Token 统计 - 完整测试")
    print("=" * 70)
    
    try:
        # 先测试 UsageExtractor
        test_usage_extractor_directly()
        
        # 测试 Token 提取
        test_token_extraction()
        
        # 测试 Burn rate
        test_burn_rate_enforcement()
        
        print("\n" + "=" * 70)
        print("✅ 所有测试通过!")
        print("=" * 70)
        
        print("\n已完成:")
        print("  ✅ Burn rate 限制 (滑动窗口 + BURN_RATE_EXCEEDED)")
        print("  ✅ Token 统计 (从工具返回值提取 usage)")
        print("  ✅ estimated=False 标记真实 usage")
        print("  ✅ 支持多种返回格式 (Dict, Object, OpenAI-style)")
        print("  ✅ BLOCKED 步骤包含 burn rate 信息")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
