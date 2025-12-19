# failcore/cli/replay_cmd.py
"""
Replay commands
"""

import json
from pathlib import Path
from failcore.core.replay import Replayer, ReplayMode


def replay_trace(args):
    """
    Replay execution from trace
    
    Two modes:
    - report: Audit mode, show what would happen
    - mock: Simulation mode, actually inject outputs
    """
    trace_path = args.trace
    mode = ReplayMode(args.mode)
    run_id = args.run
    
    if not Path(trace_path).exists():
        print(f"Error: Trace file not found: {trace_path}")
        return 1
    
    print(f"Replay Mode: {mode.value.upper()}")
    print(f"Trace: {trace_path}")
    if run_id:
        print(f"Run filter: {run_id}")
    print()
    
    # Create replayer
    replayer = Replayer(trace_path, mode=mode, run_id=run_id)
    
    # Get all steps from trace
    steps = replayer.loader.get_all_steps()
    
    if not steps:
        print("No steps found in trace")
        return 1
    
    print(f"Found {len(steps)} steps in trace")
    print()
    
    # Show replay simulation
    print("Replay Simulation:")
    print(f"{'='*80}")
    
    for idx, step_info in enumerate(steps, 1):
        _show_step_replay(idx, step_info, replayer, mode)
    
    # Show statistics
    print()
    print("Replay Statistics:")
    print(f"{'='*80}")
    stats = replayer.get_stats()
    print(f"Total Steps: {stats['total_steps']}")
    print(f"Hits: {stats['hits']} ({stats.get('hit_rate', '0%')})")
    print(f"Misses: {stats['misses']} ({stats.get('miss_rate', '0%')})")
    print(f"Diffs: {stats['diffs']} ({stats.get('diff_rate', '0%')})")
    if stats['policy_diffs'] > 0:
        print(f"  Policy Diffs: {stats['policy_diffs']}")
    if stats['output_diffs'] > 0:
        print(f"  Output Diffs: {stats['output_diffs']}")
    
    return 0


def _show_step_replay(idx: int, step_info: dict, replayer: Replayer, mode: ReplayMode):
    """Show replay simulation for a step"""
    step_id = step_info["step_id"]
    tool = step_info["tool"]
    
    # Extract info from start event
    start_evt = step_info.get("start_event", {})
    if not start_evt:
        print(f"[{idx}] {step_id} - No start event")
        return
    
    evt_data = start_evt.get("event", {})
    step_data = evt_data.get("step", {})
    fingerprint = step_data.get("fingerprint", {})
    
    data = evt_data.get("data", {})
    payload = data.get("payload", {})
    input_data = payload.get("input", {})
    params = input_data.get("summary", {})
    
    # Get end event info
    end_evt = step_info.get("end_event", {})
    status = "INCOMPLETE"
    if end_evt:
        end_data = end_evt.get("event", {}).get("data", {})
        result = end_data.get("result", {})
        status = result.get("status", "UNKNOWN")
    
    # Simulate replay
    # For report mode, we don't have current policy decision
    # So we just show what's in the trace
    
    print(f"\n[{idx}] Step: {step_id}")
    print(f"    Tool: {tool}")
    print(f"    Historical Status: {status}")
    
    if fingerprint:
        fp_id = fingerprint.get("id")
        print(f"    Fingerprint: {fp_id}")
    
    # Show what would happen
    if mode == ReplayMode.REPORT:
        print(f"    [REPORT] Would show execution timeline")
    else:
        print(f"    [MOCK] Would inject historical output")
    
    # Check for policy events
    for other_evt in step_info.get("other_events", []):
        other_evt_data = other_evt.get("event", {})
        evt_type = other_evt_data.get("type")
        
        if evt_type == "POLICY_DENIED":
            policy_data = other_evt_data.get("data", {}).get("policy", {})
            print(f"    [POLICY] Historical: DENIED - {policy_data.get('reason')}")
        
        elif evt_type == "OUTPUT_NORMALIZED":
            norm_data = other_evt_data.get("data", {}).get("normalize", {})
            if norm_data.get("decision") == "mismatch":
                print(f"    [OUTPUT] Kind mismatch: {norm_data.get('expected_kind')} -> {norm_data.get('observed_kind')}")


def replay_diff(args):
    """
    Show diffs between current rules and historical execution
    
    Useful for policy validation and regression testing
    """
    trace_path = args.trace
    
    if not Path(trace_path).exists():
        print(f"Error: Trace file not found: {trace_path}")
        return 1
    
    print(f"Replay Diff Analysis")
    print(f"Trace: {trace_path}")
    print()
    
    # Create replayer in report mode
    replayer = Replayer(trace_path, mode=ReplayMode.REPORT)
    
    # Get all steps
    steps = replayer.loader.get_all_steps()
    
    # Find steps with policy denials
    policy_denied_steps = []
    output_mismatch_steps = []
    
    for step_info in steps:
        # Check for policy denials
        for evt in step_info.get("other_events", []):
            evt_data = evt.get("event", {})
            if evt_data.get("type") == "POLICY_DENIED":
                policy_denied_steps.append(step_info)
                break
        
        # Check for output normalization issues
        for evt in step_info.get("other_events", []):
            evt_data = evt.get("event", {})
            if evt_data.get("type") == "OUTPUT_NORMALIZED":
                norm_data = evt_data.get("data", {}).get("normalize", {})
                if norm_data.get("decision") == "mismatch":
                    output_mismatch_steps.append(step_info)
                    break
    
    print(f"Analysis Results:")
    print(f"{'='*80}")
    print(f"Total Steps: {len(steps)}")
    print(f"Policy Denied: {len(policy_denied_steps)}")
    print(f"Output Mismatches: {len(output_mismatch_steps)}")
    print()
    
    if policy_denied_steps:
        print("Policy Denied Steps:")
        for step_info in policy_denied_steps[:10]:
            step_id = step_info["step_id"]
            tool = step_info["tool"]
            
            # Find policy event
            reason = "Unknown"
            for evt in step_info.get("other_events", []):
                evt_data = evt.get("event", {})
                if evt_data.get("type") == "POLICY_DENIED":
                    policy_data = evt_data.get("data", {}).get("policy", {})
                    reason = policy_data.get("reason", "Unknown")
                    break
            
            print(f"  {step_id:15s} {tool:20s} - {reason}")
        
        if len(policy_denied_steps) > 10:
            print(f"  ... and {len(policy_denied_steps) - 10} more")
        print()
    
    if output_mismatch_steps:
        print("Output Mismatch Steps:")
        for step_info in output_mismatch_steps[:10]:
            step_id = step_info["step_id"]
            tool = step_info["tool"]
            
            # Find normalize event
            expected = observed = "?"
            for evt in step_info.get("other_events", []):
                evt_data = evt.get("event", {})
                if evt_data.get("type") == "OUTPUT_NORMALIZED":
                    norm_data = evt_data.get("data", {}).get("normalize", {})
                    expected = norm_data.get("expected_kind", "?")
                    observed = norm_data.get("observed_kind", "?")
                    break
            
            print(f"  {step_id:15s} {tool:20s} - expected={expected}, got={observed}")
        
        if len(output_mismatch_steps) > 10:
            print(f"  ... and {len(output_mismatch_steps) - 10} more")
    
    return 0
