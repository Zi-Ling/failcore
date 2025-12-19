# failcore/cli/replay_cmd.py
"""
Replay 命令实现。
"""

from failcore.core.replay import TraceReplayer, ReplayMode


def replay_command(args):
    """执行 replay 命令"""
    trace_file = args.trace_file
    run_id = getattr(args, 'run', None)
    mode_str = args.mode
    
    # 转换模式
    mode_map = {
        'full': ReplayMode.FULL,
        'until_failure': ReplayMode.UNTIL_FAILURE,
        'skip_success': ReplayMode.SKIP_SUCCESS,
    }
    mode = mode_map.get(mode_str, ReplayMode.FULL)
    
    print(f"\n{'=' * 70}")
    print(f"  Trace 重放")
    print(f"{'=' * 70}")
    print(f"\n文件: {trace_file}")
    print(f"模式: {mode_str}")
    if run_id:
        print(f"Run ID: {run_id}")
    
    try:
        # 创建回放器
        replayer = TraceReplayer(trace_file)
        
        # 如果没有指定 run_id，显示可用的 run_id
        if not run_id:
            run_ids = replayer.get_run_ids()
            if len(run_ids) > 1:
                print(f"\n发现 {len(run_ids)} 个运行记录:")
                for rid in run_ids:
                    print(f"  - {rid}")
                print(f"\n提示: 使用 --run <run_id> 指定要重放的运行")
                print()
        
        # 回放
        print(f"\n开始重放:")
        print("-" * 70)
        
        result = replayer.replay(mode=mode, run_id=run_id)
        
        print("-" * 70)
        print(f"\n重放统计:")
        print(f"  总事件数: {result.total_events}")
        print(f"  已回放: {result.replayed_events}")
        print(f"  成功步骤: {result.success_count}")
        print(f"  失败步骤: {result.failure_count}")
        
        if result.failure_count > 0:
            print(f"\n失败步骤:")
            failed = replayer.get_failed_steps(run_id=run_id)
            for f in failed[:5]:  # 只显示前5个
                print(f"  ✗ {f.get('step_id')}: {f.get('error_code')}")
                msg = f.get('error_message', '')
                if msg:
                    print(f"    {msg[:60]}...")
        
        print(f"\n{'=' * 70}\n")
        
    except FileNotFoundError:
        print(f"\n✗ 错误: 找不到文件 {trace_file}")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

