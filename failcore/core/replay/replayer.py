# failcore/core/replay/replayer.py
"""
Trace 回放器。

从 trace 文件重建执行过程，用于调试和分析。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import json


class ReplayMode(str, Enum):
    """回放模式"""
    FULL = "full"              # 完整回放所有步骤
    UNTIL_FAILURE = "until_failure"  # 回放到首次失败
    SKIP_SUCCESS = "skip_success"    # 只回放失败的步骤
    STEP_BY_STEP = "step_by_step"    # 单步回放（调试模式）


@dataclass
class ReplayResult:
    """回放结果"""
    total_events: int
    replayed_events: int
    success_count: int
    failure_count: int
    events: List[Dict[str, Any]] = field(default_factory=list)
    state_snapshots: List[Dict[str, Any]] = field(default_factory=list)


class TraceReplayer:
    """
    Trace 回放器。
    
    从 trace.jsonl 文件重建执行过程。
    """
    
    def __init__(self, trace_path: str):
        """
        初始化。
        
        Args:
            trace_path: trace 文件路径
        """
        self.trace_path = trace_path
        self._events: List[Dict[str, Any]] = []
        self._load_events()
    
    def _load_events(self) -> None:
        """加载 trace 事件"""
        try:
            with open(self.trace_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        event = json.loads(line)
                        self._events.append(event)
        except Exception as e:
            print(f"加载 trace 失败: {e}")
            self._events = []
    
    def replay(
        self,
        mode: ReplayMode = ReplayMode.FULL,
        run_id: Optional[str] = None
    ) -> ReplayResult:
        """
        回放 trace。
        
        Args:
            mode: 回放模式
            run_id: 运行ID（可选，用于过滤）
            
        Returns:
            回放结果
        """
        result = ReplayResult(
            total_events=len(self._events),
            replayed_events=0,
            success_count=0,
            failure_count=0
        )
        
        for event in self._events:
            # 过滤 run_id
            if run_id and event.get("run_id") != run_id:
                continue
            
            event_type = event.get("type", "")
            
            # 根据模式决定是否回放
            should_replay = self._should_replay(event, mode, result)
            if not should_replay:
                continue
            
            # 回放事件
            self._replay_event(event, result)
            result.replayed_events += 1
            
            # 统计成功/失败
            if event_type == "STEP_OK":
                result.success_count += 1
            elif event_type == "STEP_FAIL":
                result.failure_count += 1
                
                # 如果是 UNTIL_FAILURE 模式，遇到失败就停止
                if mode == ReplayMode.UNTIL_FAILURE:
                    break
        
        return result
    
    def _should_replay(
        self,
        event: Dict[str, Any],
        mode: ReplayMode,
        result: ReplayResult
    ) -> bool:
        """判断是否应该回放该事件"""
        event_type = event.get("type", "")
        
        if mode == ReplayMode.FULL:
            return True
        
        elif mode == ReplayMode.SKIP_SUCCESS:
            # 只回放失败相关的事件
            return event_type in ("STEP_FAIL", "STEP_START")
        
        elif mode == ReplayMode.UNTIL_FAILURE:
            # 回放到首次失败
            return result.failure_count == 0
        
        return True
    
    def _replay_event(self, event: Dict[str, Any], result: ReplayResult) -> None:
        """回放单个事件"""
        # 记录事件
        result.events.append(event)
        
        # 打印事件信息（可选）
        event_type = event.get("type", "")
        step_id = event.get("step_id", "")
        tool = event.get("tool", "")
        
        if event_type == "STEP_START":
            print(f"  ▶ 开始: {step_id} ({tool})")
        elif event_type == "STEP_OK":
            duration = event.get("duration_ms", 0)
            print(f"  ✓ 成功: {step_id} ({duration}ms)")
        elif event_type == "STEP_FAIL":
            error_code = event.get("error_code", "")
            print(f"  ✗ 失败: {step_id} ({error_code})")
    
    def get_run_ids(self) -> List[str]:
        """获取所有 run_id"""
        run_ids = set()
        for event in self._events:
            run_id = event.get("run_id")
            if run_id:
                run_ids.add(run_id)
        return sorted(run_ids)
    
    def get_events_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """获取指定运行的所有事件"""
        return [e for e in self._events if e.get("run_id") == run_id]
    
    def get_failed_steps(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有失败的步骤"""
        failed = []
        for event in self._events:
            if event.get("type") == "STEP_FAIL":
                if run_id is None or event.get("run_id") == run_id:
                    failed.append(event)
        return failed
    
    def analyze(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        分析 trace。
        
        Args:
            run_id: 运行ID（可选，强烈建议指定以避免混入其他 run 的数据）
            
        Returns:
            分析结果
        """
        events = self._events
        if run_id:
            events = self.get_events_by_run(run_id)
        else:
            # 如果没有指定 run_id，检查是否有多个 run
            run_ids = set(e.get("run_id") for e in self._events if e.get("run_id"))
            if len(run_ids) > 1:
                print(f"⚠️  警告: trace 文件包含 {len(run_ids)} 个不同的 run，建议使用 --run 指定")
                print(f"   可用的 run_id: {', '.join(sorted(run_ids))}")
        
        total = len(events)
        starts = sum(1 for e in events if e.get("type") == "STEP_START")
        success = sum(1 for e in events if e.get("type") == "STEP_OK")
        failures = sum(1 for e in events if e.get("type") == "STEP_FAIL")
        
        # 统计每个工具的调用次数和耗时
        # 注意：只统计 STEP_OK 和 STEP_FAIL（真实执行次数），不统计 STEP_START
        tool_calls: Dict[str, int] = {}
        tool_durations: Dict[str, List[float]] = {}
        tool_failures: Dict[str, int] = {}
        
        for event in events:
            event_type = event.get("type")
            
            # 只统计执行完成的步骤（OK 或 FAIL）
            if event_type not in ("STEP_OK", "STEP_FAIL"):
                continue
            
            tool = event.get("tool")
            if not tool:
                continue
            
            # 计数（每个工具真实执行一次）
            tool_calls[tool] = tool_calls.get(tool, 0) + 1
            
            # 收集耗时
            duration = event.get("duration_ms")
            if duration is not None:
                if tool not in tool_durations:
                    tool_durations[tool] = []
                tool_durations[tool].append(duration)
            
            # 统计失败
            if event_type == "STEP_FAIL":
                tool_failures[tool] = tool_failures.get(tool, 0) + 1
        
        # 计算每个工具的统计信息
        tool_stats = {}
        for tool in tool_calls:
            durations = tool_durations.get(tool, [])
            tool_stats[tool] = {
                "calls": tool_calls[tool],
                "failures": tool_failures.get(tool, 0),
                "success_rate": ((tool_calls[tool] - tool_failures.get(tool, 0)) / tool_calls[tool] * 100) if tool_calls[tool] > 0 else 0,
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "total_duration_ms": sum(durations) if durations else 0,
            }
        
        # 统计错误类型和模式
        error_types: Dict[str, int] = {}
        error_patterns: List[Dict[str, Any]] = []
        
        for event in events:
            if event.get("type") == "STEP_FAIL":
                error_code = event.get("error_code", "UNKNOWN")
                error_types[error_code] = error_types.get(error_code, 0) + 1
                
                # 记录失败模式
                error_patterns.append({
                    "step_id": event.get("step_id"),
                    "tool": event.get("tool"),
                    "error_code": error_code,
                    "error_message": event.get("error_message", "")[:100],
                })
        
        # 计算总体时间统计
        durations = [
            e.get("duration_ms", 0)
            for e in events
            if e.get("duration_ms") is not None
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # 识别最慢的步骤
        slowest_steps = []
        for event in events:
            if event.get("duration_ms"):
                slowest_steps.append({
                    "step_id": event.get("step_id"),
                    "tool": event.get("tool"),
                    "duration_ms": event.get("duration_ms"),
                })
        slowest_steps.sort(key=lambda x: x["duration_ms"], reverse=True)
        slowest_steps = slowest_steps[:5]  # 只保留前5个
        
        return {
            # 总体统计
            "total_events": total,
            "step_starts": starts,
            "step_success": success,
            "step_failures": failures,
            "success_rate": (success / starts * 100) if starts > 0 else 0,
            
            # 时间统计
            "avg_duration_ms": avg_duration,
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "total_duration_ms": sum(durations),
            
            # 工具统计
            "tool_stats": tool_stats,
            
            # 错误统计
            "error_types": error_types,
            "error_patterns": error_patterns[:10],  # 只保留前10个
            
            # 性能分析
            "slowest_steps": slowest_steps,
        }
    
    def print_analysis(self, run_id: Optional[str] = None, detailed: bool = False) -> None:
        """
        打印分析结果。
        
        Args:
            run_id: 运行ID（强烈建议指定）
            detailed: 是否显示详细信息
        """
        analysis = self.analyze(run_id)
        
        print("\n" + "=" * 70)
        print("Trace 分析报告")
        if run_id:
            print(f"Run ID: {run_id}")
        else:
            print("⚠️  未指定 run_id，分析所有运行的数据")
        print("=" * 70)
        print("\n数据口径说明:")
        print("  - 执行次数 = STEP_OK + STEP_FAIL（真实执行次数）")
        print("  - 总事件数 = STEP_START + STEP_OK + STEP_FAIL")
        if run_id:
            print(f"  - 仅统计 run_id = {run_id} 的事件")
        
        # 总体统计
        print(f"\n【总体统计】")
        print(f"  总事件数: {analysis['total_events']}")
        print(f"  步骤启动: {analysis['step_starts']}")
        print(f"  成功步骤: {analysis['step_success']}")
        print(f"  失败步骤: {analysis['step_failures']}")
        print(f"  成功率: {analysis['success_rate']:.1f}%")
        
        # 时间统计
        print(f"\n【执行时间】")
        print(f"  总耗时: {analysis['total_duration_ms']:.0f}ms")
        print(f"  平均耗时: {analysis['avg_duration_ms']:.0f}ms")
        print(f"  最快: {analysis['min_duration_ms']:.0f}ms")
        print(f"  最慢: {analysis['max_duration_ms']:.0f}ms")
        
        # 工具统计
        if analysis['tool_stats']:
            print(f"\n【工具统计】（真实执行次数）")
            # 按调用次数排序
            sorted_tools = sorted(
                analysis['tool_stats'].items(),
                key=lambda x: x[1]['calls'],
                reverse=True
            )
            
            for tool, stats in sorted_tools:
                success_rate = stats['success_rate']
                status_icon = "✓" if success_rate == 100 else "⚠" if success_rate > 50 else "✗"
                
                print(f"  {status_icon} {tool}")
                print(f"      执行: {stats['calls']}次 | 失败: {stats['failures']}次 | 成功率: {success_rate:.1f}%")
                if stats['avg_duration_ms'] > 0:
                    print(f"      耗时: 平均{stats['avg_duration_ms']:.0f}ms | 最快{stats['min_duration_ms']:.0f}ms | 最慢{stats['max_duration_ms']:.0f}ms")
        
        # 错误统计
        if analysis['error_types']:
            print(f"\n【错误类型】")
            for error, count in sorted(
                analysis['error_types'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  ✗ {error}: {count}次")
        
        # 性能分析 - 最慢的步骤
        if analysis['slowest_steps'] and detailed:
            print(f"\n【性能分析 - 最慢的步骤】")
            for i, step in enumerate(analysis['slowest_steps'], 1):
                print(f"  {i}. {step['step_id']} ({step['tool']}): {step['duration_ms']:.0f}ms")
        
        # 失败模式
        if analysis['error_patterns'] and detailed:
            print(f"\n【失败模式】")
            for i, pattern in enumerate(analysis['error_patterns'], 1):
                print(f"  {i}. {pattern['step_id']} ({pattern['tool']})")
                print(f"     错误: {pattern['error_code']}")
                print(f"     信息: {pattern['error_message']}")
        
        print("\n" + "=" * 70)

