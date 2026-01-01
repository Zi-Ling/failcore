# failcore/cli/analyze_cmd.py
"""
Analyze 命令实现。
"""

from failcore.core.replay import TraceReplayer


def analyze_command(args):
    """执行 analyze 命令"""
    trace_file = args.trace_file
    run_id = getattr(args, 'run', None)
    detailed = args.detailed
    
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
                print(f"\n分析所有运行的汇总数据...")
                print()
        
        # 打印分析报告
        replayer.print_analysis(run_id=run_id, detailed=detailed)
        
    except FileNotFoundError:
        print(f"\n[ERROR] Cannot find file: {trace_file}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

