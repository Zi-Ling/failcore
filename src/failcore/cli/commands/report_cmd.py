# failcore/cli/report_cmd.py
"""
Report command - Generate HTML execution report
"""

from pathlib import Path
from failcore.infra.storage import SQLiteStore
from failcore.cli.views.trace_report import build_report_view_from_trace
from failcore.cli.renderers.html import HtmlRenderer


def register_command(subparsers):
    """Register the 'report' command and its arguments."""
    report_p = subparsers.add_parser("report", help="Generate HTML execution report")
    report_p.add_argument("--trace", help="Path to trace.jsonl file (default: last run)")
    report_p.add_argument("--html", action="store_true", default=True, help="Generate HTML format (default)")
    report_p.set_defaults(func=generate_report)


def generate_report(args):
    """
    Generate HTML execution report
    
    Usage:
    - failcore report                     # Generate report for last run
    - failcore report --html              # Same as above (--html is default)
    - failcore report --trace trace.jsonl # Generate from specific trace file
    
    Args:
        args: Command-line arguments with attributes:
            - trace: Optional path to trace.jsonl file
            - html: Boolean flag (default True)
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # If trace file is specified, use it directly
    if args.trace:
        trace_path = Path(args.trace)
        if not trace_path.exists():
            print(f"Error: Trace file not found: {trace_path}")
            return 1
        return _generate_report_from_trace(trace_path)
    
    # Otherwise, get the last run from database
    from failcore.utils.paths import get_database_path
    db_path = str(get_database_path())
    
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Hint: Run 'failcore sample' or 'failcore trace ingest <trace.jsonl>' first")
        return 1
    
    # Query database for last run
    with SQLiteStore(db_path) as store:
        cursor = store.conn.cursor()
        cursor.execute("""
            SELECT run_id, trace_path FROM runs
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if not row:
            print("Error: No runs found in database")
            return 1
        
        run_id = row["run_id"]
        trace_path_str = row["trace_path"]
        
        if not trace_path_str:
            print(f"Error: Run {run_id} has no associated trace file")
            return 1
        
        trace_path = Path(trace_path_str)
        if not trace_path.exists():
            print(f"Error: Trace file not found: {trace_path}")
            return 1
        
        return _generate_report_from_trace(trace_path)


def _generate_report_from_trace(trace_path: Path) -> int:
    """
    Generate HTML report from trace file
    
    Args:
        trace_path: Path to trace.jsonl file
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Build view model from trace
        view = build_report_view_from_trace(trace_path)
        
        # Render to HTML
        renderer = HtmlRenderer()
        html_content = renderer.render_trace_report(view)
        
        # Save to file (same directory as trace, with _report.html suffix)
        report_path = trace_path.parent / f"{trace_path.stem}_report.html"
        report_path.write_text(html_content, encoding='utf-8')
        
        print(f"✓ HTML report generated: {report_path}")
        return 0
        
    except Exception as e:
        print(f"Error: Failed to generate report: {e}")
        return 1
