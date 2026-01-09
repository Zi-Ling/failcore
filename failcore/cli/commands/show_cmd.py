# failcore/cli/show_cmd.py
"""
Show command - Display run/step details from database
"""

from pathlib import Path
from failcore.infra.storage import SQLiteStore


def register_command(subparsers):
    """Register the 'show' command and its arguments."""
    show_p = subparsers.add_parser("show", help="Show run/step details")
    show_p.add_argument("--run", help="Show specific run_id")
    show_p.add_argument("--last", action="store_true", help="Show last run (default)")
    show_p.add_argument("--steps", action="store_true", help="Show steps list")
    show_p.add_argument("--errors", action="store_true", help="Show only errors/blocked")
    show_p.add_argument("--step", help="Show specific step detail")
    show_p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    show_p.set_defaults(func=show_trace)


def show_trace(args):
    """
    Show run/step details from database
    
    Usage:
    - failcore show                    # Show last run
    - failcore show --last             # Show last run
    - failcore show --run <run_id>     # Show specific run
    - failcore show --steps            # Show steps list
    - failcore show --errors           # Only errors/blocked
    - failcore show --step <step_id>   # Show step detail
    """
    from failcore.utils.paths import get_database_path
    db_path = str(get_database_path())
    
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Hint: Run 'failcore trace ingest <trace.jsonl>' first")
        return 1
    
    run_id = args.run
    show_last = args.last or (not run_id and not args.step)  # Default to last
    show_steps = args.steps
    show_errors = args.errors
    step_id = args.step
    verbose = args.verbose
    
    with SQLiteStore(db_path) as store:
        # Get run_id
        if show_last or not run_id:
            # Get last run
            cursor = store.conn.cursor()
            cursor.execute("""
                SELECT run_id FROM runs
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                print("No runs found in database")
                return 1
            run_id = row["run_id"]
        
        # Show step detail
        if step_id:
            return _show_step_detail(store, run_id, step_id, verbose)
        
        # Show run summary
        return _show_run_summary(store, run_id, show_steps, show_errors, verbose)


def _show_run_summary(store: SQLiteStore, run_id: str, show_steps: bool, show_errors: bool, verbose: bool):
    """Show run summary and optionally steps"""
    cursor = store.conn.cursor()
    
    # Get run info
    cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    run = cursor.fetchone()
    
    if not run:
        print(f"Run not found: {run_id}")
        return 1
    
    # Print run header
    print("="*80)
    print(f"Run: {run['run_id']}")
    print("="*80)
    print(f"Created: {run['created_at']}")
    if run['trace_path']:
        print(f"Trace: {run['trace_path']}")
    print(f"Events: {run['total_events']}")
    print(f"Steps: {run['total_steps']}")
    print()
    
    # Get steps
    where_clause = "WHERE run_id = ?"
    params = [run_id]
    
    if show_errors:
        where_clause += " AND status IN ('BLOCKED', 'FAIL')"
    
    cursor.execute(f"""
        SELECT step_id, tool, status, phase, duration_ms, error_code, error_message,
               has_policy_denied, has_output_normalized
        FROM steps
        {where_clause}
        ORDER BY start_ts
    """, params)
    
    steps = cursor.fetchall()
    
    if not steps:
        print("No steps found" + (" (no errors)" if show_errors else ""))
        return 0
    
    # Print steps
    if show_steps or show_errors:
        print("Steps:")
        print("-"*80)
        for idx, step in enumerate(steps, 1):
            _print_step_row(idx, step, verbose)
    else:
        # Summary only
        status_counts = {}
        for step in steps:
            status = step['status'] or 'UNKNOWN'
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("Status Summary:")
        for status, count in sorted(status_counts.items()):
            marker = {
                'OK': '[OK]',
                'FAIL': '[FAIL]',
                'BLOCKED': '[BLOCKED]',
            }.get(status, f'[{status}]')
            print(f"  {marker:12s} {count}")
        
        print()
        print("Use --steps to see step list")
        print("Use --errors to see only errors")
        print(f"Use --step <step_id> to see step details")
    
    return 0


def _print_step_row(idx: int, step: dict, verbose: bool):
    """Print a single step row"""
    status_marker = {
        'OK': '[OK]',
        'FAIL': '[FAIL]',
        'BLOCKED': '[BLOCKED]',
        'INCOMPLETE': '[INCOMPLETE]',
    }.get(step['status'], f"[{step['status']}]")
    
    print(f"\n[{idx}] {step['step_id']}")
    print(f"    Tool: {step['tool']}")
    print(f"    Status: {status_marker}")
    
    if step['duration_ms']:
        print(f"    Duration: {step['duration_ms']}ms")
    
    if step['has_policy_denied']:
        print(f"    [POLICY] Denied")
    
    if step['has_output_normalized']:
        print(f"    [OUTPUT] Normalized")
    
    if step['error_code']:
        print(f"    Error: {step['error_code']}")
        if verbose and step['error_message']:
            print(f"      {step['error_message']}")


def _show_step_detail(store: SQLiteStore, run_id: str, step_id: str, verbose: bool):
    """Show detailed step information"""
    cursor = store.conn.cursor()
    
    # Get step
    cursor.execute("""
        SELECT * FROM steps
        WHERE run_id = ? AND step_id = ?
    """, (run_id, step_id))
    
    step = cursor.fetchone()
    
    if not step:
        print(f"Step not found: {step_id} in run {run_id}")
        return 1
    
    # Print step detail
    print("="*80)
    print(f"Step: {step['step_id']}")
    print("="*80)
    print(f"Run: {step['run_id']}")
    print(f"Tool: {step['tool']}")
    print(f"Attempt: {step['attempt']}")
    print(f"Status: {step['status']}")
    print(f"Phase: {step['phase']}")
    print()
    
    print("Timing:")
    print(f"  Started: {step['start_ts']}")
    print(f"  Finished: {step['end_ts']}")
    print(f"  Duration: {step['duration_ms']}ms")
    print()
    
    if step['fingerprint_id']:
        print(f"Fingerprint: {step['fingerprint_id']}")
        print()
    
    # Flags
    flags = []
    if step['has_policy_denied']:
        flags.append("Policy Denied")
    if step['has_output_normalized']:
        flags.append("Output Normalized")
    
    if flags:
        print("Flags:")
        for flag in flags:
            print(f"  - {flag}")
        print()
    
    # Error
    if step['error_code']:
        print("Error:")
        print(f"  Code: {step['error_code']}")
        print(f"  Message: {step['error_message']}")
        print()
    
    # Get related events if verbose
    if verbose:
        cursor.execute("""
            SELECT seq, ts, type, level
            FROM events
            WHERE run_id = ? AND step_id = ?
            ORDER BY seq
        """, (run_id, step_id))
        
        events = cursor.fetchall()
        
        if events:
            print("Events:")
            for evt in events:
                print(f"  [{evt['seq']:3d}] {evt['type']:25s} ({evt['level']})")
    
    return 0
