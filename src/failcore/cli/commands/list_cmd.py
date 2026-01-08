# failcore/cli/list_cmd.py
"""
List command - List recent runs from database
"""

from pathlib import Path
from datetime import datetime
from failcore.infra.storage import SQLiteStore


def register_command(subparsers):
    """Register the 'list' command and its arguments."""
    list_p = subparsers.add_parser("list", help="List recent runs")
    list_p.add_argument("--limit", type=int, default=10, help="Number of runs to show (default: 10)")
    list_p.set_defaults(func=list_runs)


def list_runs(args):
    """
    List recent runs from database
    
    Shows:
    - Run ID
    - Created time
    - Duration
    - Status (OK/FAIL/BLOCKED counts)
    - Tool calls
    """
    from failcore.utils.paths import get_database_path
    db_path = str(get_database_path())
    
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Hint: Run 'failcore sample' or 'failcore trace ingest <trace.jsonl>' first")
        return 1
    
    limit = getattr(args, 'limit', 10)
    
    with SQLiteStore(db_path) as store:
        cursor = store.conn.cursor()
        
        # Get runs with aggregated step info
        cursor.execute("""
            SELECT 
                r.run_id,
                r.created_at,
                r.first_event_ts,
                r.last_event_ts,
                r.total_events,
                r.total_steps,
                r.trace_path
            FROM runs r
            ORDER BY r.created_at DESC
            LIMIT ?
        """, (limit,))
        
        runs = cursor.fetchall()
        
        if not runs:
            print("No runs found in database")
            return 0
        
        # Print header
        print("="*150)
        print(f"Recent Runs (showing {len(runs)} of {len(runs)})")
        print("="*150)
        print()
        
        # Print table header
        print(f"{'Run ID':<20} {'Created':<20} {'Duration':<10} {'Steps':<7} {'Result':<12} {'Tools':<40} {'Status':<30}")
        print("-"*150)
        
        # Print each run
        for run in runs:
            run_id = run['run_id']
            created_at = run['created_at']
            first_ts = run['first_event_ts']
            last_ts = run['last_event_ts']
            total_steps = run['total_steps']
            
            # Calculate duration
            duration_str = _calculate_duration(first_ts, last_ts)
            
            # Get step status counts
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM steps
                WHERE run_id = ?
                GROUP BY status
            """, (run_id,))
            
            status_counts = {}
            for row in cursor.fetchall():
                status_counts[row['status']] = row['count']
            
            # Get tools used in this run
            cursor.execute("""
                SELECT DISTINCT tool
                FROM steps
                WHERE run_id = ?
                ORDER BY tool
            """, (run_id,))
            
            tools = [row['tool'] for row in cursor.fetchall()]
            tools_str = ", ".join(tools) if tools else "N/A"
            # Truncate if too long
            if len(tools_str) > 38:
                tools_str = tools_str[:35] + "..."
            
            # Determine overall result
            result_str = _determine_result(status_counts, total_steps)
            
            # Format status (detailed breakdown)
            status_parts = []
            if status_counts.get('OK', 0) > 0:
                status_parts.append(f"OK:{status_counts['OK']}")
            if status_counts.get('BLOCKED', 0) > 0:
                status_parts.append(f"BLOCKED:{status_counts['BLOCKED']}")
            if status_counts.get('FAIL', 0) > 0:
                status_parts.append(f"FAIL:{status_counts['FAIL']}")
            
            status_str = " ".join(status_parts) if status_parts else "INCOMPLETE"
            
            # Format created time (shorter)
            created_short = _format_time(created_at)
            
            # Print row
            print(f"{run_id:<20} {created_short:<20} {duration_str:<10} {total_steps:<7} {result_str:<12} {tools_str:<40} {status_str:<30}")
        
        print()
        print(f"Use 'failcore show --run <run_id>' to see details")
        print(f"Use 'failcore show' to see last run")
    
    return 0


def _calculate_duration(first_ts: str, last_ts: str) -> str:
    """Calculate duration between two ISO timestamps"""
    if not first_ts or not last_ts:
        return "N/A"
    
    try:
        # Parse ISO format timestamps
        first = datetime.fromisoformat(first_ts.replace('Z', '+00:00'))
        last = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
        
        duration = (last - first).total_seconds()
        
        if duration < 1:
            return f"{int(duration * 1000)}ms"
        elif duration < 60:
            return f"{duration:.1f}s"
        else:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes}m{seconds}s"
    except:
        return "N/A"


def _format_time(timestamp: str) -> str:
    """Format ISO timestamp to shorter readable format"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        # Format as: Dec 21 20:30:09
        return dt.strftime("%b %d %H:%M:%S")
    except:
        return timestamp[:19] if len(timestamp) > 19 else timestamp


def _determine_result(status_counts: dict, total_steps: int) -> str:
    """
    Determine overall result from step status counts
    
    Logic:
    - FAIL: any step failed
    - BLOCKED: any step blocked (policy denied) and no failures
    - SUCCESS: all steps completed OK
    - PARTIAL: some steps completed, not all
    - INCOMPLETE: no completed steps
    """
    ok_count = status_counts.get('OK', 0)
    blocked_count = status_counts.get('BLOCKED', 0)
    fail_count = status_counts.get('FAIL', 0)
    
    # Priority: FAIL > BLOCKED > SUCCESS > PARTIAL > INCOMPLETE
    if fail_count > 0:
        return "FAIL"
    elif blocked_count > 0:
        return "BLOCKED"
    elif ok_count == total_steps and total_steps > 0:
        return "SUCCESS"
    elif ok_count > 0:
        return "PARTIAL"
    else:
        return "INCOMPLETE"
