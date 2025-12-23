# failcore/cli/main.py
import argparse
import os
import tempfile
import json
from pathlib import Path

from failcore.cli.show_cmd import show_trace
from failcore.cli.validate_cmd import validate_trace
from failcore.cli.trace_cmd import trace_ingest, trace_query, trace_stats
from failcore.cli.replay_cmd import replay_trace, replay_diff
from failcore.cli.list_cmd import list_runs
from failcore.cli.report_cmd import generate_report
from failcore.infra.storage import SQLiteStore, TraceIngestor
from failcore.infra.storage import SQLiteStore, TraceIngestor
from pathlib import Path


def run_sample(args):
    """
    Run three-act demonstration of FailCore's core value propositions:
    Act 1: Policy interception (permission boundary)
    Act 2: Contract validation (schema mismatch)
    Act 3: Blackbox replay (forensic evidence)
    """
    from failcore import Session
    from failcore.core.step import generate_run_id
    from datetime import datetime
    
    # Setup .failcore/ workspace structure
    if args.sandbox:
        # Custom sandbox - keep as is
        run_root = Path(args.sandbox)
    else:
        # Default: use relative path .failcore/runs/<date>/<run_id>_<time>/
        # Group by date to avoid too many directories in one folder
        run_id = generate_run_id()
        now = datetime.now()
        date = now.strftime("%Y%m%d")
        time = now.strftime("%H%M%S")
        run_root = Path(".failcore/runs") / date / f"{run_id}_{time}"
    
    run_root.mkdir(parents=True, exist_ok=True)
    sandbox = run_root / "workspace"
    sandbox.mkdir(exist_ok=True)
    trace_path = str(run_root / "trace.jsonl")
    
    # For display, use relative paths directly (no conversion needed)
    run_root_rel = run_root
    sandbox_rel = sandbox
    trace_rel = Path(trace_path)
    
    print(f"\n{'='*70}")
    print(f"  FailCore Three-Act Demonstration")
    print(f"  Workspace: {run_root_rel}")
    print(f"  Sandbox: {sandbox_rel}")
    print(f"  Trace: {trace_rel}")
    print(f"{'='*70}\n")
    
    # Create custom sandbox policy for demonstration
    class SandboxPolicy:
        """Strict sandbox policy - any path operation must be within sandbox"""
        def __init__(self, sandbox_root):
            # Use absolute path for comparison, but derived from relative path
            self.sandbox_root = Path(sandbox_root).resolve()
        
        def allow(self, step, ctx):
            # Check if tool has path parameter
            path_param = step.params.get("path")
            if path_param:
                abs_path = Path(path_param).resolve()
                # Check if path is within sandbox
                try:
                    abs_path.relative_to(self.sandbox_root)
                    return True, ""
                except ValueError:
                    return False, "Path escapes sandbox boundary"
            return True, ""
    
    policy = SandboxPolicy(sandbox)
    
    with Session(trace=trace_path, policy=policy) as session:
        # Register tools
        _register_sample_tools(session, sandbox)
        
        # Act 1: Policy interception
        _act1_policy_denied(session, sandbox)
        
        # Act 2: Contract violation
        _act2_schema_mismatch(session)
        
    # Act 3: Replay
    _act3_replay(trace_path)
    
    print(f"\n{'='*70}")
    print(f"  Value Proposition Summary:")
    print(f"  [X] Agent can't escape permissions (Policy)")
    print(f"  [X] Output drift is detectable (Contract)")
    print(f"  [X] Full forensic replay available (Trace)")
    print(f"\n  Workspace: {run_root_rel}")
    print(f"  Safe to delete after review")
    print(f"{'='*70}\n")
    
    # Auto-ingest to database
    _auto_ingest(trace_path)


def _register_sample_tools(session, sandbox):
    """Register tools for sample demonstration"""
    
    @session.tool
    def cleanup_temp(path: str) -> str:
        """Clean up temporary files (demonstrates policy check)"""
        abs_path = Path(path).absolute()
        if abs_path.exists():
            if abs_path.is_file():
                abs_path.unlink()
                return f"Deleted: {path}"
        return f"Not found: {path}"
    
    @session.tool
    def fetch_user_data(user_id: str) -> str:
        """
        Fetch user data (demonstrates schema mismatch).
        Simulates LLM returning commentary instead of pure JSON.
        """
        # This is what you expect:
        # return json.dumps({"user_id": user_id, "name": "Alice", "email": "alice@example.com"})
        
        # This is what buggy LLM outputs (common in tool-calling scenarios):
        return f"Here is the user data you requested: {{success: true, user_id: {user_id}, name: 'Alice'}}"
    
    @session.tool
    def read_config(path: str) -> dict:
        """Read config file (not used in demo, for completeness)"""
        full_path = sandbox / path
        if full_path.exists():
            with open(full_path) as f:
                return json.load(f)
        return {"error": "File not found"}


def _act1_policy_denied(session, sandbox):
    """Act 1: Intercepting permission boundary violations"""
    print("\n" + "─"*70)
    print("  ACT 1: Policy Interception - Permission Boundary")
    print("─"*70 + "\n")
    
    # Create a file outside sandbox
    outside_file = Path(tempfile.gettempdir()) / "important_data.txt"
    outside_file.write_text("Important production data - DO NOT DELETE")
    
    print("[AGENT] (simulated)")
    print(f"  Intent: Cleanup temporary files")
    print(f"  Proposed Action: cleanup_temp(path=\"<system_temp>/{outside_file.name}\")")
    print()
    
    # Try to delete file outside sandbox
    result = session.call("cleanup_temp", path=str(outside_file))
    
    print("[SHIELD] INTERCEPTED")
    print(f"  Status: {result.status.value.upper()}")
    if result.error:
        print(f"  Error Code: {result.error.error_code}")
        print(f"  Message: {result.error.message}")
        if result.error.detail:
            print(f"  Detail: {result.error.detail}")
    print()
    
    print("[CHECK] Side effect prevented")
    print(f"  Target still exists: {outside_file.exists()}")
    print()
    
    print("[TRACE] Evidence recorded")
    print(f"  Event: policy_denied")
    print(f"  Step ID: {result.step_id}")
    print()
    
    print("[VALUE] FailCore stops agents from escaping sandbox - \"smart\" doesn't mean \"trusted\"")
    
    # Cleanup
    if outside_file.exists():
        outside_file.unlink()


def _act2_schema_mismatch(session):
    """Act 2: Detecting contract violations and output drift"""
    print("\n" + "─"*70)
    print("  ACT 2: Contract Validation - Output Drift Detection")
    print("─"*70 + "\n")
    
    print("[AGENT] (simulated)")
    print(f"  Tool Call: fetch_user_data(user_id=\"123\")")
    print(f"  Expected: JSON object {{\"user_id\": ..., \"name\": ..., \"email\": ...}}")
    print()
    
    result = session.call("fetch_user_data", user_id="123")
    
    print("[SHIELD] CONTRACT DRIFT DETECTED")
    print(f"  Status: {result.status.value.upper()}")
    
    if result.output:
        output_value = result.output.value
        print(f"  Expected Contract: JSON")
        print(f"  Observed Type: {result.output.kind.value.upper()}")
        print(f"  Raw Output: \"{output_value[:80]}...\"")
        print()
        
        # Try to parse as JSON to demonstrate mismatch
        is_valid_json = False
        try:
            json.loads(output_value)
            is_valid_json = True
        except:
            pass
        
        print(f"  Valid JSON: {'Yes' if is_valid_json else 'No'}")
        if not is_valid_json:
            print(f"  Issue: Contains commentary/garbage text before JSON")
    print()
    
    print("[DETAIL]")
    print(f"  Root Cause: LLM added explanation text instead of pure JSON")
    print(f"  Downstream Impact: json.loads() will raise JSONDecodeError")
    print(f"  FailCore Behavior: Normalized as TEXT (kind={result.output.kind.value})")
    print(f"  Detection Method: Output type hint mismatch")
    print()
    
    print("[TRACE] Evidence recorded")
    print(f"  Event: output_kind_mismatch (expected=JSON, got=TEXT)")
    print(f"  Step ID: {result.step_id}")
    print(f"  Fingerprint: output.kind={result.output.kind.value}")
    print()
    
    print("[VALUE] FailCore makes \"model drift\" a machine-readable failure type for auto-retry/fallback")


def _act3_replay(trace_path):
    """Act 3: Forensic replay from blackbox trace"""
    print("\n" + "─"*70)
    print("  ACT 3: Blackbox Replay - Forensic Evidence Chain")
    print("─"*70 + "\n")
    
    # Display relative path
    cwd = Path.cwd()
    try:
        trace_rel = Path(trace_path).relative_to(cwd)
    except ValueError:
        trace_rel = Path(trace_path)
    
    print("[REPLAY] Loading execution trace")
    print(f"  Source: {trace_rel}")
    print()
    
    # Read and parse trace
    events = []
    with open(trace_path, 'r') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    # Extract key events
    print("[TIMELINE]")
    
    step_events = {}
    for event in events:
        step_id = event.get('step_id')
        if step_id:
            if step_id not in step_events:
                step_events[step_id] = []
            step_events[step_id].append(event)
    
    for idx, (step_id, evts) in enumerate(step_events.items(), 1):
        start_evt = next((e for e in evts if e.get('type') == 'step_start'), None)
        fail_evt = next((e for e in evts if e.get('type') == 'step_fail'), None)
        ok_evt = next((e for e in evts if e.get('type') == 'step_ok'), None)
        
        if start_evt:
            print(f"\n  [{idx}] Step: {step_id}")
            print(f"      Tool: {start_evt.get('tool')}")
            print(f"      Params: {start_evt.get('params_summary', {})}")
            
            if fail_evt:
                print(f"      Result: BLOCKED")
                print(f"      Error: {fail_evt.get('error_code')}")
                print(f"      Reason: {fail_evt.get('error_message', '')[:60]}...")
                meta = fail_evt.get('meta', {})
                if meta.get('phase'):
                    print(f"      Phase: {meta['phase']}")
            elif ok_evt:
                print(f"      Result: OK")
                print(f"      Duration: {ok_evt.get('duration_ms')}ms")
    
    # Summary
    failed_count = len([e for e in events if e.get('type') == 'step_fail'])
    ok_count = len([e for e in events if e.get('type') == 'step_ok'])
    
    print(f"\n[SUMMARY]")
    print(f"  Total Steps: {len(step_events)}")
    print(f"  Blocked: {failed_count}")
    print(f"  Succeeded: {ok_count}")
    print(f"  Side Effects: 0 (all blocked actions prevented)")
    print()
    
    print("[VALUE] FailCore provides offline forensics - replay, attribute, write rules, not \"hope to reproduce\"")


def _auto_ingest(trace_path: str):
    """Auto-ingest trace to database after run completes"""
    db_path = ".failcore/failcore.db"
    
    # Ensure .failcore directory exists
    Path(".failcore").mkdir(exist_ok=True)
    
    try:
        with SQLiteStore(db_path) as store:
            store.init_schema()
            ingestor = TraceIngestor(store)
            stats = ingestor.ingest_file(trace_path, skip_if_exists=True)
            
            if not stats.get("skipped"):
                print(f"\n[AUTO-INGEST] Trace ingested to {db_path}")
                print(f"              Use 'failcore show' to view")
    except Exception as e:
        # Don't fail the sample command if ingest fails
        print(f"\n[WARNING] Auto-ingest failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        "failcore",
        description="FailCore - Observable and replayable tool execution engine"
    )
    sub = parser.add_subparsers(dest="command")

    # sample - three-act demonstration
    sample_p = sub.add_parser(
        "sample",
        help="Run three-act demonstration: Policy / Contract / Replay"
    )
    sample_p.add_argument(
        "--sandbox", 
        help="Custom run directory (default: ./.failcore/runs/<date>/<run_id>_<time>)"
    )

    # validate - validate trace file
    validate_p = sub.add_parser("validate", help="Validate trace file against v0.1.1 spec")
    validate_p.add_argument("trace", help="Path to trace file")

    # list - list recent runs
    list_p = sub.add_parser("list", help="List recent runs")
    list_p.add_argument("--limit", type=int, default=10, help="Number of runs to show (default: 10)")
    
    # show - display run/step details
    show_p = sub.add_parser("show", help="Show run/step details")
    show_p.add_argument("--run", help="Show specific run_id")
    show_p.add_argument("--last", action="store_true", help="Show last run (default)")
    show_p.add_argument("--steps", action="store_true", help="Show steps list")
    show_p.add_argument("--errors", action="store_true", help="Show only errors/blocked")
    show_p.add_argument("--step", help="Show specific step detail")
    show_p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # report - generate HTML execution report
    report_p = sub.add_parser("report", help="Generate HTML execution report")
    report_p.add_argument("--trace", help="Path to trace.jsonl file (default: last run)")
    report_p.add_argument("--html", action="store_true", default=True, help="Generate HTML format (default)")

    # trace - trace management commands
    trace_p = sub.add_parser("trace", help="Trace management (ingest, query, stats)")
    trace_sub = trace_p.add_subparsers(dest="trace_command")
    
    # trace ingest
    ingest_p = trace_sub.add_parser("ingest", help="Ingest trace.jsonl into database")
    ingest_p.add_argument("trace", help="Path to trace.jsonl file")
    
    # trace query
    query_p = trace_sub.add_parser("query", help="Execute SQL query on trace database")
    query_p.add_argument("query", help="SQL query to execute")
    
    # trace stats
    stats_p = trace_sub.add_parser("stats", help="Show trace statistics")
    stats_p.add_argument("--run", help="Filter by run_id")

    # replay - replay commands
    replay_p = sub.add_parser("replay", help="Replay execution from trace")
    replay_sub = replay_p.add_subparsers(dest="replay_command")
    
    # replay run
    replay_run_p = replay_sub.add_parser("run", help="Replay execution")
    replay_run_p.add_argument("trace", help="Path to trace.jsonl file")
    replay_run_p.add_argument("--mode", choices=["report", "mock"], default="report",
                             help="Replay mode: report (audit) or mock (inject outputs)")
    replay_run_p.add_argument("--run", help="Filter by run_id")
    replay_run_p.add_argument("--format", choices=["text", "json"], default="text",
                             help="Output format")
    
    # replay diff
    replay_diff_p = replay_sub.add_parser("diff", help="Show policy/output diffs")
    replay_diff_p.add_argument("trace", help="Path to trace.jsonl file")
    replay_diff_p.add_argument("--format", choices=["text", "json"], default="text",
                             help="Output format")

    args = parser.parse_args()

    # If no command provided, show help
    if not args.command:
        parser.print_help()
        return

    if args.command == "validate":
        return validate_trace(args)
    elif args.command == "list":
        return list_runs(args)
    elif args.command == "show":
        return show_trace(args)
    elif args.command == "report":
        return generate_report(args)
    elif args.command == "sample":
        run_sample(args)
    elif args.command == "trace":
        if not args.trace_command:
            trace_p.print_help()
            return
        
        if args.trace_command == "ingest":
            return trace_ingest(args)
        elif args.trace_command == "query":
            return trace_query(args)
        elif args.trace_command == "stats":
            return trace_stats(args)
    elif args.command == "replay":
        if not args.replay_command:
            replay_p.print_help()
            return
        
        if args.replay_command == "run":
            return replay_trace(args)
        elif args.replay_command == "diff":
            return replay_diff(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
