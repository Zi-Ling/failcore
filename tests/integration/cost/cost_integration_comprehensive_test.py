"""
Cost Integration Comprehensive Test

验证6个关键点:
1. 真实超预算必拦截
2. meta.cost_per_call 真正生效
3. Token 统计
4. Burn rate 限制
5. 统一 metrics.cost schema
6. Trace 真实落盘

这个测试会创建真实的 trace 文件并验证所有功能
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone

from failcore.core.executor import Executor, ExecutorConfig
from failcore.core.tools import ToolRegistry
from failcore.core.step import Step, RunContext
from failcore.core.trace import TraceRecorder
from failcore.core.cost import CostGuardian, CostEstimator, CostUsage


class RealTraceRecorder(TraceRecorder):
    """真实的 Trace Recorder - 写入 jsonl 文件"""
    
    def __init__(self, trace_file: Path):
        self.trace_file = trace_file
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self.events = []
        
        # 清空文件
        with open(self.trace_file, 'w') as f:
            pass
    
    def next_seq(self):
        self._seq += 1
        return self._seq
    
    def record(self, event):
        event_dict = event.to_dict()
        self.events.append(event_dict)
        
        # 立即写入文件
        with open(self.trace_file, 'a') as f:
            f.write(json.dumps(event_dict) + '\n')


def rebuild_cost_curve_from_trace(trace_file: Path):
    """从 trace 文件重建成本曲线"""
    print(f"\n📊 从 trace 重建成本曲线: {trace_file}")
    print("=" * 70)
    
    if not trace_file.exists():
        print("❌ Trace 文件不存在!")
        return
    
    steps = []
    with open(trace_file) as f:
        for line in f:
            if not line.strip():
                continue
            
            event = json.loads(line)
            if event["event"]["type"] == "STEP_END":
                step_info = event["event"].get("step", {})
                data = event["event"].get("data", {})
                result = data.get("result", {})
                metrics = data.get("metrics", {})
                
                step_id = step_info.get("id", "unknown")
                tool = step_info.get("tool", "unknown")
                status = result.get("status", "UNKNOWN")
                
                cost_info = metrics.get("cost", {})
                incremental = cost_info.get("incremental", {})
                cumulative = cost_info.get("cumulative", {})
                
                steps.append({
                    "step_id": step_id,
                    "tool": tool,
                    "status": status,
                    "incremental_usd": incremental.get("cost_usd", 0.0),
                    "incremental_tokens": incremental.get("tokens", 0),
                    "cumulative_usd": cumulative.get("cost_usd", 0.0),
                    "cumulative_tokens": cumulative.get("tokens", 0),
                    "error": result.get("error", {}).get("code"),
                })
    
    print(f"{'Step':<6} {'Tool':<15} {'Status':<10} {'Δ Cost':<12} {'Cumul':<12} {'Tokens':<10}")
    print("-" * 70)
    
    for s in steps:
        symbol = "✓" if s["status"] == "OK" else "✗"
        print(f"{symbol} {s['step_id']:<4} {s['tool']:<15} {s['status']:<10} "
              f"${s['incremental_usd']:>10.6f} ${s['cumulative_usd']:>10.6f} {s['cumulative_tokens']:>8}")
        
        if s["error"]:
            print(f"  └─ 🛑 {s['error']}")
    
    print("=" * 70)
    
    if steps:
        final = steps[-1]
        print(f"✅ 最终累计: ${final['cumulative_usd']:.6f}, {final['cumulative_tokens']} tokens")
    
    return steps


def test_1_budget_enforcement():
    """测试1: 真实超预算必拦截"""
    print("\n" + "=" * 70)
    print("测试 1: 真实超预算必拦截")
    print("=" * 70)
    
    # 设置很小的预算
    guardian = CostGuardian(max_cost_usd=0.5)  # 只有 $0.50
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("cheap_tool", lambda x: f"result: {x}")
    tools.register("expensive_tool", lambda x: f"expensive result: {x}")
    
    trace_file = Path(".failcore/test_runs/test1_budget/trace.jsonl")
    recorder = RealTraceRecorder(trace_file)
    
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
        meta={"cost_usd": 0.1},  # $0.10
    )
    
    result1 = executor.execute(step1, ctx)
    print(f"Step 1: status={result1.status.value}, error={result1.error.error_code if result1.error else None}")
    assert result1.status.value == "ok", "Step 1 should succeed"
    
    # Step 2: 昂贵的工具 (应该被拦截)
    step2 = Step(
        id="s2",
        tool="expensive_tool",
        params={"x": "big task"},
        meta={"cost_usd": 1.0},  # $1.00 - 超过剩余预算!
    )
    
    result2 = executor.execute(step2, ctx)
    print(f"Step 2: status={result2.status.value}, error={result2.error.error_code if result2.error else None}")
    
    # 验证
    assert result2.status.value == "blocked", f"Step 2 should be blocked, got {result2.status.value}"
    assert result2.error.error_code == "BUDGET_EXCEEDED", f"Should be BUDGET_EXCEEDED, got {result2.error.error_code}"
    
    print("✅ 测试通过: 超预算被正确拦截")
    
    # 重建曲线验证
    steps = rebuild_cost_curve_from_trace(trace_file)
    assert len(steps) == 2, f"Should have 2 steps, got {len(steps)}"
    assert steps[1]["status"] == "BLOCKED", "Step 2 should be BLOCKED in trace"
    assert steps[1]["cumulative_usd"] > 0, "Blocked step should have cumulative cost"
    
    return trace_file


def test_2_meta_cost_priority():
    """测试2: meta.cost_usd 优先级正确"""
    print("\n" + "=" * 70)
    print("测试 2: meta.cost_usd 优先级")
    print("=" * 70)
    
    guardian = CostGuardian(max_cost_usd=10.0)
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("tool1", lambda: "result")
    
    trace_file = Path(".failcore/test_runs/test2_meta/trace.jsonl")
    recorder = RealTraceRecorder(trace_file)
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test2-meta",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # 使用 meta.cost_usd 显式指定成本
    step = Step(
        id="s1",
        tool="tool1",
        params={},
        meta={"cost_usd": 2.5, "tokens": 1000},  # 显式指定
    )
    
    result = executor.execute(step, ctx)
    print(f"Result: status={result.status.value}")
    
    # 验证 trace 中的成本
    steps = rebuild_cost_curve_from_trace(trace_file)
    assert len(steps) == 1
    assert abs(steps[0]["incremental_usd"] - 2.5) < 0.001, f"Should be $2.5, got ${steps[0]['incremental_usd']}"
    assert steps[0]["incremental_tokens"] == 1000, f"Should be 1000 tokens, got {steps[0]['incremental_tokens']}"
    
    print("✅ 测试通过: meta.cost_usd 正确生效")
    
    return trace_file


def test_3_cumulative_tracking():
    """测试3: 累计成本追踪"""
    print("\n" + "=" * 70)
    print("测试 3: 累计成本追踪")
    print("=" * 70)
    
    guardian = CostGuardian(max_cost_usd=10.0)
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("tool", lambda x: f"result: {x}")
    
    trace_file = Path(".failcore/test_runs/test3_cumulative/trace.jsonl")
    recorder = RealTraceRecorder(trace_file)
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test3-cumulative",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # 执行多个步骤
    costs = [0.5, 1.0, 1.5, 2.0]
    for i, cost in enumerate(costs):
        step = Step(
            id=f"s{i+1}",
            tool="tool",
            params={"x": i},
            meta={"cost_usd": cost},
        )
        result = executor.execute(step, ctx)
        print(f"Step {i+1}: cost=${cost}, status={result.status.value}")
    
    # 验证累计
    steps = rebuild_cost_curve_from_trace(trace_file)
    assert len(steps) == 4
    
    expected_cumulative = 0.0
    for i, step in enumerate(steps):
        expected_cumulative += costs[i]
        actual = step["cumulative_usd"]
        assert abs(actual - expected_cumulative) < 0.001, \
            f"Step {i+1}: expected ${expected_cumulative}, got ${actual}"
    
    print(f"✅ 测试通过: 累计成本正确 (${expected_cumulative})")
    
    return trace_file


def test_4_blocked_step_has_metrics():
    """测试4: BLOCKED 步骤包含 cost metrics"""
    print("\n" + "=" * 70)
    print("测试 4: BLOCKED 步骤包含 cost metrics")
    print("=" * 70)
    
    guardian = CostGuardian(max_cost_usd=1.0)
    estimator = CostEstimator()
    
    tools = ToolRegistry()
    tools.register("tool", lambda: "result")
    
    trace_file = Path(".failcore/test_runs/test4_blocked_metrics/trace.jsonl")
    recorder = RealTraceRecorder(trace_file)
    
    executor = Executor(
        tools=tools,
        recorder=recorder,
        cost_guardian=guardian,
        cost_estimator=estimator,
        config=ExecutorConfig(enable_cost_tracking=True),
    )
    
    ctx = RunContext(
        run_id="test4-blocked",
        created_at=datetime.now(timezone.utc).isoformat(),
        sandbox_root="/tmp/test",
        cwd="/tmp/test",
    )
    
    # 第一步成功
    step1 = Step(id="s1", tool="tool", params={}, meta={"cost_usd": 0.3})
    executor.execute(step1, ctx)
    
    # 第二步超预算
    step2 = Step(id="s2", tool="tool", params={}, meta={"cost_usd": 1.5})
    result2 = executor.execute(step2, ctx)
    
    assert result2.status.value == "blocked", f"Should be blocked, got {result2.status.value}"
    
    # 验证 BLOCKED 步骤有 metrics
    steps = rebuild_cost_curve_from_trace(trace_file)
    blocked_step = steps[1]
    
    assert blocked_step["status"] == "blocked" or blocked_step["status"] == "BLOCKED"
    assert blocked_step["cumulative_usd"] > 0, "BLOCKED step must have cumulative cost"
    assert blocked_step["incremental_usd"] > 0, "BLOCKED step must have incremental cost"
    
    print(f"✅ 测试通过: BLOCKED 步骤包含 metrics (cumulative=${blocked_step['cumulative_usd']})")
    
    return trace_file


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("Cost Integration Comprehensive Test")
    print("=" * 70)
    
    trace_files = []
    
    try:
        trace_files.append(test_1_budget_enforcement())
        trace_files.append(test_2_meta_cost_priority())
        trace_files.append(test_3_cumulative_tracking())
        trace_files.append(test_4_blocked_step_has_metrics())
        
        print("\n" + "=" * 70)
        print("✅ 所有测试通过!")
        print("=" * 70)
        
        print("\n生成的 trace 文件:")
        for tf in trace_files:
            if tf and tf.exists():
                size = tf.stat().st_size
                print(f"  - {tf} ({size} bytes)")
        
        print("\n关键验证点:")
        print("  ✅ 1. 超预算必拦截 (BLOCKED status)")
        print("  ✅ 2. meta.cost_usd 优先级正确")
        print("  ✅ 3. 累计成本追踪准确")
        print("  ✅ 4. BLOCKED 步骤包含 cost metrics")
        print("  ✅ 5. Trace 文件可重建成本曲线")
        
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
