# failcore/cli/show_cmd.py
"""
Trace viewing command with multiple views
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any


def show_trace(args):
    """Show trace with various views"""
    trace_path = args.trace
    
    if not Path(trace_path).exists():
        print(f"Error: File not found: {trace_path}")
        return 1
    
    # Load events
    events = []
    with open(trace_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    if not events:
        print("No valid events found in trace")
        return 1
    
    # Route to appropriate view
    if args.steps:
        show_steps_table(events)
    elif args.errors:
        show_errors(events)
    elif args.step:
        show_step_detail(events, args.step, args.verbose)
    elif args.stats:
        show_stats(events)
    elif args.run:
        show_run(events, args.run)
    else:
        # Default: summary
        show_summary(events)
    
    return 0


def show_summary(events: List[Dict[str, Any]]):
    """Show trace summary"""
    runs = set()
    steps = set()
    event_types = defaultdict(int)
    
    for evt in events:
        run_id = evt.get("run", {}).get("run_id")
        if run_id:
            runs.add(run_id)
        
        event_type = evt.get("event", {}).get("type")
        if event_type:
            event_types[event_type] += 1
        
        step = evt.get("event", {}).get("step", {})
        if step.get("id"):
            steps.add(step["id"])
    
    print(f"Trace Summary")
    print(f"{'='*60}")
    print(f"Total Events: {len(events)}")
    print(f"Runs: {len(runs)}")
    print(f"Steps: {len(steps)}")
    print()
    print(f"Event Types:")
    for evt_type, count in sorted(event_types.items()):
        print(f"  {evt_type:25s} {count:5d}")


def show_steps_table(events: List[Dict[str, Any]]):
    """Show steps as a table"""
    steps = {}
    
    for evt in events:
        event = evt.get("event", {})
        step = event.get("step", {})
        step_id = step.get("id")
        
        if not step_id:
            continue
        
        if step_id not in steps:
            steps[step_id] = {
                "id": step_id,
                "tool": step.get("tool", ""),
                "attempt": step.get("attempt", 1),
                "status": "PENDING",
                "phase": "-",
                "duration_ms": 0,
            }
        
        if event.get("type") == "STEP_END":
            data = event.get("data", {})
            result = data.get("result", {})
            steps[step_id].update({
                "status": result.get("status", "UNKNOWN"),
                "phase": result.get("phase", "-"),
                "duration_ms": result.get("duration_ms", 0),
            })
    
    print(f"Steps Table")
    print(f"{'='*100}")
    print(f"{'ID':<12} {'Tool':<20} {'Attempt':<8} {'Status':<10} {'Phase':<10} {'Duration (ms)':>15}")
    print(f"{'-'*100}")
    
    for step in sorted(steps.values(), key=lambda s: s["id"]):
        print(f"{step['id']:<12} {step['tool']:<20} {step['attempt']:<8} {step['status']:<10} {step['phase']:<10} {step['duration_ms']:>15}")


def show_errors(events: List[Dict[str, Any]]):
    """Show aggregated errors"""
    policy_denies = []
    blocked = []
    schema_mismatches = []
    other_errors = []
    
    for evt in events:
        event = evt.get("event", {})
        evt_type = event.get("type")
        
        if evt_type == "POLICY_DENIED":
            policy_denies.append(evt)
        elif evt_type == "OUTPUT_NORMALIZED":
            data = event.get("data", {})
            normalize = data.get("normalize", {})
            if normalize.get("decision") == "mismatch":
                schema_mismatches.append(evt)
        elif evt_type == "STEP_END":
            data = event.get("data", {})
            result = data.get("result", {})
            if result.get("status") == "BLOCKED":
                blocked.append(evt)
            elif result.get("status") == "FAIL":
                other_errors.append(evt)
    
    print(f"Errors Summary")
    print(f"{'='*60}")
    print(f"Policy Denies: {len(policy_denies)}")
    print(f"Blocked Steps: {len(blocked)}")
    print(f"Schema Mismatches: {len(schema_mismatches)}")
    print(f"Other Failures: {len(other_errors)}")
    print()
    
    if policy_denies:
        print(f"Policy Denies:")
        for evt in policy_denies[:5]:
            event = evt.get("event", {})
            step = event.get("step", {})
            data = event.get("data", {})
            policy = data.get("policy", {})
            print(f"  [{evt.get('seq', '?')}] {step.get('id', '?'):12} - {policy.get('reason', 'No reason')}")
        if len(policy_denies) > 5:
            print(f"  ... and {len(policy_denies) - 5} more")
        print()
    
    if schema_mismatches:
        print(f"Schema Mismatches:")
        for evt in schema_mismatches[:5]:
            event = evt.get("event", {})
            step = event.get("step", {})
            data = event.get("data", {})
            normalize = data.get("normalize", {})
            print(f"  [{evt.get('seq', '?')}] {step.get('id', '?'):12} - expected={normalize.get('expected_kind')}, got={normalize.get('observed_kind')}")
        if len(schema_mismatches) > 5:
            print(f"  ... and {len(schema_mismatches) - 5} more")


def show_step_detail(events: List[Dict[str, Any]], step_id: str, verbose: bool):
    """Show detailed lifecycle for a specific step"""
    step_events = []
    for evt in events:
        event = evt.get("event", {})
        step = event.get("step", {})
        if step.get("id") == step_id:
            step_events.append(evt)
    
    if not step_events:
        print(f"No events found for step: {step_id}")
        return
    
    print(f"Step Detail: {step_id}")
    print(f"{'='*80}")
    
    for evt in step_events:
        seq = evt.get("seq", "?")
        ts = evt.get("ts", "?")[:19]  # Truncate timestamp
        event = evt.get("event", {})
        evt_type = event.get("type", "UNKNOWN")
        
        print(f"[{seq:3}] {ts} {evt_type}")
        
        if verbose:
            # Show more details
            if evt_type == "STEP_START":
                data = event.get("data", {})
                payload = data.get("payload", {})
                inp = payload.get("input", {})
                print(f"     Tool: {event.get('step', {}).get('tool')}")
                print(f"     Params: {inp.get('summary', {})}")
            elif evt_type == "STEP_END":
                data = event.get("data", {})
                result = data.get("result", {})
                print(f"     Status: {result.get('status')}")
                print(f"     Phase: {result.get('phase')}")
                print(f"     Duration: {result.get('duration_ms')}ms")
                if result.get("error"):
                    error = result["error"]
                    print(f"     Error: [{error.get('code')}] {error.get('message')}")
            elif evt_type == "POLICY_DENIED":
                data = event.get("data", {})
                policy = data.get("policy", {})
                print(f"     Rule: {policy.get('rule_id')} - {policy.get('rule_name')}")
                print(f"     Reason: {policy.get('reason')}")
        print()


def show_stats(events: List[Dict[str, Any]]):
    """Show statistics"""
    policy_denies = 0
    kind_mismatches = 0
    durations = []
    status_counts = defaultdict(int)
    phase_counts = defaultdict(int)
    
    for evt in events:
        event = evt.get("event", {})
        evt_type = event.get("type")
        
        if evt_type == "POLICY_DENIED":
            policy_denies += 1
        elif evt_type == "OUTPUT_NORMALIZED":
            data = event.get("data", {})
            if data.get("normalize", {}).get("decision") == "mismatch":
                kind_mismatches += 1
        elif evt_type == "STEP_END":
            data = event.get("data", {})
            result = data.get("result", {})
            status = result.get("status")
            phase = result.get("phase")
            duration = result.get("duration_ms", 0)
            
            if status:
                status_counts[status] += 1
            if phase:
                phase_counts[phase] += 1
            if duration:
                durations.append(duration)
    
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    print(f"Trace Statistics")
    print(f"{'='*60}")
    print(f"Policy Denies: {policy_denies}")
    print(f"Output Kind Mismatches: {kind_mismatches}")
    print(f"Average Duration: {avg_duration:.2f}ms")
    print()
    print(f"Status Distribution:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:15s} {count:5d}")
    print()
    print(f"Phase Distribution:")
    for phase, count in sorted(phase_counts.items()):
        print(f"  {phase:15s} {count:5d}")


def show_run(events: List[Dict[str, Any]], run_id: str):
    """Show events for specific run"""
    run_events = [evt for evt in events if evt.get("run", {}).get("run_id") == run_id]
    
    if not run_events:
        print(f"No events found for run: {run_id}")
        return
    
    print(f"Run: {run_id}")
    print(f"{'='*80}")
    print(f"Events: {len(run_events)}")
    print()
    
    # Show timeline
    for evt in run_events[:20]:  # Show first 20
        seq = evt.get("seq", "?")
        ts = evt.get("ts", "?")[:19]
        evt_type = evt.get("event", {}).get("type", "UNKNOWN")
        step = evt.get("event", {}).get("step", {})
        step_id = step.get("id", "")
        
        print(f"[{seq:3}] {ts} {evt_type:25s} {step_id}")
    
    if len(run_events) > 20:
        print(f"... and {len(run_events) - 20} more events")
