"""
Cost Integration Production-Ready Tests

修复了测试代码的9个问题:
1. 覆盖所有6个关键点（包括 schema contract 和 burn rate）
2. 统一 status 枚举对比（使用 StepStatus）
3. 测试 cost_per_call vs cost_usd 优先级
4. 标准化 token 字段映射
5. 严格断言 blocked step metrics 存在
6. 使用默认 trace 路径（.failcore/runs/...）
7. 添加 schema contract 测试
8. 添加 burn rate 测试壳子
9. 添加 token 提取测试壳子
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from failcore.core.executor import Executor, ExecutorConfig
from failcore.core.tools import ToolRegistry
from failcore.core.step import Step, RunContext, StepStatus
from failcore.core.trace import TraceRecorder
from failcore.core.cost import CostGuardian, CostEstimator, CostUsage


class FileTraceRecorder(TraceRecorder):
    """生产级 Trace Recorder - 持有文件句柄"""
    
    def __init__(self, trace_file: Path):
        self.trace_file = trace_file
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self.events = []
        
        # 持有文件句柄
        self._file = open(self.trace_file, 'w', encoding='utf-8')
    
    def next_seq(self):
        self._seq += 1
        return self._seq
    
    def record(self, event):
        event_dict = event.to_dict()
        self.events.append(event_dict)
        
        # 写入并flush
        self._file.write(json.dumps(event_dict) + '\n')
        self._file.flush()
    
    def close(self):
        if self._file and not self._file.closed:
            self._file.close()
    
    def __del__(self):
        self.close()


def assert_metrics_schema(metrics: Dict[str, Any], step_id: str):
    """
    严格断言 metrics.cost schema
    
    确保符合契约:
    - metrics.cost 存在
    - metrics.cost.incremental 存在并包含必要字段
    - metrics.cost.cumulative 存在并包含必要字段
    """
    assert metrics is not None, f"{step_id}: metrics must exist"
    assert "cost" in metrics, f"{step_id}: metrics.cost must exist"
    
    cost = metrics["cost"]
    
    # 检查 incremental
    assert "incremental" in cost, f"{step_id}: metrics.cost.incremental must exist"
    incr = cost["incremental"]
    assert "cost_usd" in incr, f"{step_id}: incremental.cost_usd must exist"
    assert "tokens" in incr, f"{step_id}: incremental.tokens must exist"
    assert "api_calls" in incr, f"{step_id}: incremental.api_calls must exist"
    assert "estimated" in incr, f"{step_id}: incremental.estimated must exist"
    
    # 检查 cumulative
    assert "cumulative" in cost, f"{step_id}: metrics.cost.cumulative must exist"
    cumul = cost["cumulative"]
    assert "cost_usd" in cumul, f"{step_id}: cumulative.cost_usd must exist"
    assert "tokens" in cumul, f"{step_id}: cumulative.tokens must exist"
    assert "api_calls" in cumul, f"{step_id}: cumulative.api_calls must exist"


def rebuild_cost_curve(trace_file: Path):
    """从 trace 重建成本曲线（带 schema 验证）"""
    print(f"\n📊 从 trace 重建成本曲线: {trace_file}")
    print("=" * 70)
    
    if not trace_file.exists():
        print("❌ Trace 文件不存在!")
        return []
    
    steps = []
    with open(trace_file, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            
            event = json.loads(line)
            if event["event"]["type"] == "STEP_END":
                step_info = event["event"].get("step", {})
                data = event["event"].get("data", {})
                result = data.get("result", {})
                metrics = data.get("metrics")
                
                step_id = step_info.get("id", "unknown")
                tool = step_info.get("tool", "unknown")
                status = result.get("status", "UNKNOWN").upper()  # 统一大写
                
                # 如果有 metrics，验证 schema
                if metrics:
                    assert_metrics_schema(metrics, step_id)
                    cost_info = metrics.get("cost", {})
                    incremental = cost_info.get("incremental", {})
                    cumulative = cost_info.get("cumulative", {})
                else:
                    incremental = {}
                    cumulative = {}
                
                steps.append({
                    "step_id": step_id,
                    "tool": tool,
                    "status": status,
                    "incremental_usd": incremental.get("cost_usd", None),
                    "incremental_tokens": incremental.get("tokens", None),
                    "cumulative_usd": cumulative.get("cost_usd", None),
                    "cumulative_tokens": cumulative.get("tokens", None),
                    "has_metrics": metrics is not None,
                    "error": result.get("error", {}).get("code"),
                })
    
    print(f"{'Step':<6} {'Tool':<15} {'Status':<10} {'Δ Cost':<12} {'Cumul':<12} {'Metrics':<8}")
    print("-" * 70)
    
    for s in steps:
        symbol = "✓" if s["status"] == "OK" else "✗"
        delta_str = f"${s['incremental_usd']:.6f}" if s['incremental_usd'] is not None else "N/A"
        cumul_str = f"${s['cumulative_usd']:.6f}" if s['cumulative_usd'] is not None else "N/A"
        metrics_str = "✓" if s['has_metrics'] else "✗"
        
        print(f"{symbol} {s['step_id']:<4} {s['tool']:<15} {s['status']:<10} "
              f"{delta_str:>10} {cumul_str:>10}   {metrics_str}")
        
        if s["error"]:
            print(f"  └─ 🛑 {s['error']}")
    
    print("=" * 70)
    
    return steps


def test_1_budget_enforcement():
    """测试1: 真实超预算必拦截"""
    print("\n" + "=" * 70)
    print("测试 1: 真实超预算必拦截")
    print("=" * 70)
    
    guardian = CostGuardian(max_cost_usd=0.5)
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("cheap_tool", lambda x: f"result: {x}")
    tools.register("expensive_tool", lambda x: f"expensive result: {x}")
    
    trace_file = Path(".failcore/runs/test1_budget/trace.jsonl")
    recorder = FileTraceRecorder(trace_file)
    
    try:
        executor = Executor(
            tools=tools,
            recorder=recorder,
            cost_guardian=guardian,
            cost_estimator=estimator,
            config=ExecutorConfig(enable_cost_tracking=True),
        )
        
        ctx = RunContext(
            run_id="test1-budget",
            created_at=datetime.now(timezone.utc).isoformat(),
            sandbox_root="/tmp/test",
            cwd="/tmp/test",
        )
        
        # Step 1: 便宜的工具 (应该成功)
        step1 = Step(
            id="s1",
            tool="cheap_tool",
            params={"x": "test"},
            meta={"cost_usd": 0.1},
        )
        
        result1 = executor.execute(step1, ctx)
        print(f"Step 1: status={result1.status}, error={result1.error.error_code if result1.error else None}")
        assert result1.status == StepStatus.OK, "Step 1 should succeed"
        
        # Step 2: 昂贵的工具 (应该被拦截)
        step2 = Step(
            id="s2",
            tool="expensive_tool",
            params={"x": "big task"},
            meta={"cost_usd": 1.0},
        )
        
        result2 = executor.execute(step2, ctx)
        print(f"Step 2: status={result2.status}, error={result2.error.error_code if result2.error else None}")
        
        # 使用枚举对比
        assert result2.status == StepStatus.BLOCKED, f"Step 2 should be BLOCKED, got {result2.status}"
        assert result2.error.error_code == "BUDGET_EXCEEDED"
        
        print("✅ 测试通过: 超预算被正确拦截")
        
    finally:
        recorder.close()
    
    # 重建曲线验证
    steps = rebuild_cost_curve(trace_file)
    assert len(steps) == 2
    assert steps[1]["status"] == "BLOCKED"
    
    # 严格检查 BLOCKED 步骤有 metrics
    assert steps[1]["has_metrics"], "BLOCKED step must have metrics"
    assert steps[1]["cumulative_usd"] is not None, "BLOCKED step must have cumulative_usd"
    assert steps[1]["cumulative_usd"] > 0, f"BLOCKED step cumulative must > 0, got {steps[1]['cumulative_usd']}"
    
    print("✅ Trace 验证通过")
    return trace_file


def test_2_cost_priority():
    """测试2: cost_per_call vs cost_usd 优先级"""
    print("\n" + "=" * 70)
    print("测试 2: cost_per_call vs cost_usd 优先级")
    print("=" * 70)
    
    guardian = CostGuardian(max_cost_usd=10.0)
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("tool1", lambda: "result")
    
    trace_file = Path(".failcore/runs/test2_priority/trace.jsonl")
    recorder = FileTraceRecorder(trace_file)
    
    try:
        executor = Executor(
            tools=tools,
            recorder=recorder,
            cost_guardian=guardian,
            cost_estimator=estimator,
            config=ExecutorConfig(enable_cost_tracking=True),
        )
        
        ctx = RunContext(
            run_id="test2-priority",
            created_at=datetime.now(timezone.utc).isoformat(),
            sandbox_root="/tmp/test",
            cwd="/tmp/test",
        )
        
        # Case 1: 只有 cost_per_call
        step1 = Step(
            id="s1",
            tool="tool1",
            params={},
            meta={"cost_per_call": 0.5},
        )
        executor.execute(step1, ctx)
        
        # Case 2: cost_usd 优先于 cost_per_call
        step2 = Step(
            id="s2",
            tool="tool1",
            params={},
            meta={
                "cost_usd": 2.5,  # 应该使用这个
                "cost_per_call": 0.1,  # 被忽略
                "total_tokens": 1000,
            },
        )
        executor.execute(step2, ctx)
        
    finally:
        recorder.close()
    
    # 验证优先级
    steps = rebuild_cost_curve(trace_file)
    assert len(steps) == 2
    
    # Case 1: cost_per_call 生效
    assert abs(steps[0]["incremental_usd"] - 0.5) < 0.001, \
        f"cost_per_call should be 0.5, got {steps[0]['incremental_usd']}"
    
    # Case 2: cost_usd 优先
    assert abs(steps[1]["incremental_usd"] - 2.5) < 0.001, \
        f"cost_usd should override cost_per_call, got {steps[1]['incremental_usd']}"
    
    # Case 2: tokens 也生效
    assert steps[1]["incremental_tokens"] == 1000, \
        f"tokens should be 1000, got {steps[1]['incremental_tokens']}"
    
    print("✅ 测试通过: 优先级正确 (cost_usd > cost_per_call)")
    return trace_file


def test_3_schema_contract():
    """测试3: metrics.cost schema 契约"""
    print("\n" + "=" * 70)
    print("测试 3: metrics.cost Schema 契约")
    print("=" * 70)
    
    guardian = CostGuardian(max_cost_usd=10.0)
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("tool", lambda x: f"result: {x}")
    
    trace_file = Path(".failcore/runs/test3_schema/trace.jsonl")
    recorder = FileTraceRecorder(trace_file)
    
    try:
        executor = Executor(
            tools=tools,
            recorder=recorder,
            cost_guardian=guardian,
            cost_estimator=estimator,
            config=ExecutorConfig(enable_cost_tracking=True),
        )
        
        ctx = RunContext(
            run_id="test3-schema",
            created_at=datetime.now(timezone.utc).isoformat(),
            sandbox_root="/tmp/test",
            cwd="/tmp/test",
        )
        
        # 执行多个步骤
        for i in range(3):
            step = Step(
                id=f"s{i+1}",
                tool="tool",
                params={"x": i},
                meta={"cost_usd": 0.5 * (i+1), "total_tokens": 100 * (i+1)},
            )
            executor.execute(step, ctx)
        
    finally:
        recorder.close()
    
    # 验证 schema（rebuild_cost_curve 内部会做断言）
    steps = rebuild_cost_curve(trace_file)
    
    # 所有步骤都必须有 metrics
    for step in steps:
        assert step["has_metrics"], f"{step['step_id']} must have metrics"
        assert step["incremental_usd"] is not None
        assert step["cumulative_usd"] is not None
        assert step["incremental_tokens"] is not None
        assert step["cumulative_tokens"] is not None
    
    # 验证累计正确
    expected_cumul = 0.0
    expected_tokens = 0
    for i, step in enumerate(steps):
        expected_cumul += 0.5 * (i+1)
        expected_tokens += 100 * (i+1)
        
        assert abs(step["cumulative_usd"] - expected_cumul) < 0.001
        assert step["cumulative_tokens"] == expected_tokens
    
    print("✅ 测试通过: Schema 契约正确")
    return trace_file


def test_4_burn_rate_placeholder():
    """测试4: Burn rate 限制（测试壳子）"""
    print("\n" + "=" * 70)
    print("测试 4: Burn rate 限制（待实现）")
    print("=" * 70)
    
    # TODO: 实现真实 burn rate 测试
    # 需要:
    # 1. BurnRateLimiter 支持时间窗口
    # 2. 在 executor 中检查 burn rate
    # 3. 快速连续提交高 cost 操作
    # 4. 断言触发 BURN_RATE_EXCEEDED
    
    print("⏳ Burn rate 测试待实现")
    print("   需要: 滑动窗口 + 时间桶 + BURN_RATE_EXCEEDED 错误码")
    
    # 测试壳子 - 至少验证 guardian 有 burn_limiter
    guardian = CostGuardian(
        max_cost_usd=10.0,
        max_usd_per_minute=1.0,  # $1/min 限制
    )
    
    assert guardian.burn_limiter is not None, "Guardian should have burn_limiter"
    print("✓ BurnRateLimiter 已初始化")


def test_5_token_extraction_placeholder():
    """测试5: 真实 token 统计（测试壳子）"""
    print("\n" + "=" * 70)
    print("测试 5: 真实 Token 统计（待实现）")
    print("=" * 70)
    
    # TODO: 实现真实 token 提取
    # 需要:
    # 1. 模拟 LLM adapter 返回 usage
    # 2. Executor 提取 usage.input_tokens/output_tokens
    # 3. 写入 metrics.cost（estimated=False）
    # 4. 断言 trace 中有真实 token 数据
    
    print("⏳ Token 提取测试待实现")
    print("   需要: LLM adapter hook + usage 提取 + estimated=False")
    
    # 测试壳子 - 验证 CostUsage 支持 estimated 字段
    usage = CostUsage(
        run_id="test",
        step_id="s1",
        tool_name="llm_generate",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost_usd=0.01,
        estimated=False,  # 真实数据
    )
    
    assert usage.estimated == False, "CostUsage should support estimated=False"
    print("✓ CostUsage 支持 estimated 字段")


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("Cost Integration Production-Ready Tests")
    print("=" * 70)
    
    trace_files = []
    
    try:
        trace_files.append(test_1_budget_enforcement())
        trace_files.append(test_2_cost_priority())
        trace_files.append(test_3_schema_contract())
        test_4_burn_rate_placeholder()
        test_5_token_extraction_placeholder()
        
        print("\n" + "=" * 70)
        print("✅ 所有测试通过!")
        print("=" * 70)
        
        print("\n生成的 trace 文件:")
        for tf in trace_files:
            if tf and tf.exists():
                size = tf.stat().st_size
                print(f"  - {tf} ({size} bytes)")
        
        print("\n已完成:")
        print("  ✅ 1. 超预算必拦截 (BLOCKED + metrics)")
        print("  ✅ 2. cost_usd > cost_per_call 优先级")
        print("  ✅ 3. Schema 契约测试 (incremental/cumulative)")
        print("  ✅ 4. Trace 文件可重建成本曲线")
        print("  ✅ 5. 状态枚举统一 (StepStatus)")
        print("  ✅ 6. BLOCKED 步骤严格验证 metrics 存在")
        
        print("\n待实现:")
        print("  ⏳ Burn rate 限制 (需要滑动窗口)")
        print("  ⏳ 真实 token 统计 (需要 LLM adapter)")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
