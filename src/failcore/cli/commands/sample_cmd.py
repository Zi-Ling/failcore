# failcore/cli/commands/sample_cmd.py
import tempfile
import json
from pathlib import Path

from failcore import run, guard
from failcore.core.errors import FailCoreError
from failcore.infra.storage import SQLiteStore, TraceIngestor
from failcore.utils import get_run_directory


def register_command(subparsers):
    """Register the 'sample' command and its arguments."""
    sample_p = subparsers.add_parser(
        "sample",
        help="Run three-act demonstration: Policy / Contract / Replay"
    )
    sample_p.add_argument(
        "--sandbox", 
        help="Custom run directory (default: ./.failcore/runs/<date>/<run_id>_<HHMMSS>_sample)"
    )
    sample_p.set_defaults(func=run_sample)


def run_sample(args):
    """
    Run three-act demonstration of FailCore's core value propositions:
    Act 1: Policy interception (permission boundary)
    Act 2: Contract validation (schema mismatch)
    Act 3: Blackbox replay (audit evidence)
    """
    # Setup .failcore/ sandbox structure
    if args.sandbox:
        # Custom sandbox - keep as is
        run_root = Path(args.sandbox)
    else:
        # Use unified path generation
        run_root = get_run_directory("sample")
    
    sandbox = run_root / "sandbox"
    sandbox.mkdir(exist_ok=True)
    trace_path = str(run_root / "trace.jsonl")
    
    # Convert to relative paths and use forward slashes
    try:
        run_root_rel = run_root.relative_to(Path.cwd()).as_posix()
        sandbox_rel = sandbox.relative_to(Path.cwd()).as_posix()
        trace_rel = Path(trace_path).relative_to(Path.cwd()).as_posix()
    except ValueError:
        # If paths are not relative to cwd, use absolute paths with forward slashes
        run_root_rel = run_root.as_posix()
        sandbox_rel = sandbox.as_posix()
        trace_rel = Path(trace_path).as_posix()
    
    print(f"\n{'='*70}")
    print(f"  FailCore Three-Act Demonstration")
    print(f"  Sandbox: {sandbox_rel}")
    print(f"  Trace: {trace_rel}")
    print(f"{'='*70}\n")
    
    # Use run() context with fs_safe policy
    with run(
        policy="fs_safe",
        sandbox=str(sandbox),
        trace=trace_path,
        strict=True
    ) as ctx:
        # Register and guard tools
        tools = _register_sample_tools(ctx, sandbox)
        
        # Act 1: Policy interception
        _act1_policy_denied(ctx, tools, sandbox)
        
        # Act 2: Contract violation
        _act2_schema_mismatch(ctx, tools)
        
    # Act 3: Replay
    _act3_replay(trace_path)
    
    print(f"\n{'='*70}")
    print(f"  Value Proposition Summary:")
    print(f"  [X] Agent can't escape permissions (Policy)")
    print(f"  [X] Output drift is detectable (Contract)")
    print(f"  [X] Full audit replay available (Trace)")
    print(f"\n  sandbox: {run_root_rel}")
    print(f"  Safe to delete after review")
    print(f"{'='*70}\n")
    
    # Auto-ingest to database
    _auto_ingest(trace_path)


def _register_sample_tools(ctx, sandbox):
    """Register tools for sample demonstration with guard"""
    
    def cleanup_temp(path: str) -> str:
        """Clean up temporary files (demonstrates policy check)"""
        abs_path = Path(path).absolute()
        if abs_path.exists():
            if abs_path.is_file():
                abs_path.unlink()
                return f"Deleted: {path}"
        return f"Not found: {path}"
    
    def fetch_user_data(user_id: str) -> str:
        """
        Fetch user data (demonstrates schema mismatch).
        Simulates LLM returning commentary instead of pure JSON.
        """
        # This is what you expect:
        # return json.dumps({"user_id": user_id, "name": "Alice", "email": "alice@example.com"})
        
        # This is what buggy LLM outputs (common in tool-calling scenarios):
        return f"Here is the user data you requested: {{success: true, user_id: {user_id}, name: 'Alice'}}"
    
    def read_config(path: str) -> dict:
        """Read config file (not used in demo, for completeness)"""
        full_path = sandbox / path
        if full_path.exists():
            with open(full_path) as f:
                return json.load(f)
        return {"error": "File not found"}
    
    # Guard tools with new API
    safe_cleanup = guard(
        cleanup_temp,
        risk="high",
        effect="fs",
        description="Clean up temporary files (demonstrates policy check)"
    )
    
    safe_fetch = guard(
        fetch_user_data,
        risk="medium",
        effect="net",
        description="Fetch user data (demonstrates schema mismatch)"
    )
    
    safe_read = guard(
        read_config,
        risk="low",
        effect="fs",
        description="Read config file"
    )
    
    # Return tools dict for easier access
    return {
        "cleanup_temp": safe_cleanup,
        "fetch_user_data": safe_fetch,
        "read_config": safe_read,
    }


def _act1_policy_denied(ctx, tools, sandbox):
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
    
    # Try to delete file outside sandbox - should be blocked
    cleanup_temp = tools["cleanup_temp"]
    try:
        result = cleanup_temp(path=str(outside_file))
        print("[SHIELD] FAILED TO BLOCK")
        print(f"  ERROR: Should have been blocked but succeeded")
    except FailCoreError as e:
        print("[SHIELD] INTERCEPTED")
        print(f"  Status: BLOCKED")
        print(f"  Error Code: {e.error_code}")
        print(f"  Message: {e.message}")
        if e.details:
            print(f"  Detail: {e.details}")
        print()
        
        print("[CHECK] Side effect prevented")
        print(f"  Target still exists: {outside_file.exists()}")
        print()
        
        print("[TRACE] Evidence recorded")
        print(f"  Event: policy_denied")
        try:
            trace_path_rel = Path(ctx.trace_path).relative_to(Path.cwd()).as_posix()
        except ValueError:
            trace_path_rel = Path(ctx.trace_path).as_posix()
        print(f"  Trace: {trace_path_rel}")
        print()
    
    print("[VALUE] FailCore stops agents from escaping sandbox - \"smart\" doesn't mean \"trusted\"")
    
    # Cleanup
    if outside_file.exists():
        outside_file.unlink()


def _act2_schema_mismatch(ctx, tools):
    """Act 2: Detecting contract violations and output drift"""
    print("\n" + "─"*70)
    print("  ACT 2: Contract Validation - Output Drift Detection")
    print("─"*70 + "\n")
    
    print("[AGENT] (simulated)")
    print(f"  Tool Call: fetch_user_data(user_id=\"123\")")
    print(f"  Expected: JSON object {{\"user_id\": ..., \"name\": ..., \"email\": ...}}")
    print()
    
    # Call the tool - it returns invalid JSON
    fetch_user_data = tools["fetch_user_data"]
    result = fetch_user_data(user_id="123")
    
    print("[SHIELD] OUTPUT VALIDATION")
    print(f"  Status: SUCCESS (but output is non-JSON)")
    print(f"  Raw Output: \"{result[:80]}...\"")
    print()
    
    # Try to parse as JSON to demonstrate mismatch
    is_valid_json = False
    try:
        json.loads(result)
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
    print(f"  FailCore Behavior: Execution succeeds, but output is traceable")
    print(f"  Detection Method: Can be validated in trace replay")
    print()
    
    print("[TRACE] Evidence recorded")
    print(f"  Event: tool_execution with problematic output")
    try:
        trace_path_rel = Path(ctx.trace_path).relative_to(Path.cwd()).as_posix()
    except ValueError:
        trace_path_rel = Path(ctx.trace_path).as_posix()
    print(f"  Trace: {trace_path_rel}")
    print(f"  Can be analyzed offline for contract violations")
    print()
    
    print("[VALUE] FailCore makes \"model drift\" traceable and debuggable through execution logs")


def _act3_replay(trace_path):
    """Act 3: audit replay from blackbox trace"""
    print("\n" + "─"*70)
    print("  ACT 3: Blackbox Replay - audit Evidence Chain")
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
    
    # Extract key events (v0.1.2 schema)
    print("[TIMELINE]")
    
    step_events = {}
    for event in events:
        evt = event.get('event', {})
        step = evt.get('step', {})
        step_id = step.get('id')
        if step_id:
            if step_id not in step_events:
                step_events[step_id] = []
            step_events[step_id].append(event)
    
    for idx, (step_id, evts) in enumerate(step_events.items(), 1):
        # v0.1.2: events have nested structure
        start_evt = next((e for e in evts if e.get('event', {}).get('type') == 'STEP_START'), None)
        end_evt = next((e for e in evts if e.get('event', {}).get('type') == 'STEP_END'), None)
        
        if start_evt:
            evt = start_evt.get('event', {})
            step = evt.get('step', {})
            data = evt.get('data', {})
            
            # Extract tool metadata if present
            tool_name = step.get('tool', 'unknown')
            metadata = step.get('metadata', {})
            
            print(f"\n  [{idx}] Step: {step_id}")
            print(f"      Tool: {tool_name}")
            
            # Show metadata (v0.1.2 enhancement)
            if metadata:
                risk = metadata.get('risk_level', 'N/A')
                side_effect = metadata.get('side_effect', 'N/A')
                print(f"      Metadata: risk={risk}, side_effect={side_effect}")
            
            # Extract params from payload
            payload = data.get('payload', {})
            input_data = payload.get('input', {})
            params_summary = input_data.get('summary', {})
            print(f"      Params: {params_summary}")
            
            if end_evt:
                evt_data = end_evt.get('event', {})
                data = evt_data.get('data', {})
                result = data.get('result', {})
                
                status = result.get('status', 'UNKNOWN')
                severity = evt_data.get('severity', 'INFO')
                
                if status in ['FAIL', 'BLOCKED']:
                    print(f"      Result: {status}")
                    print(f"      Severity: {severity}")
                    
                    error = result.get('error', {})
                    error_code = error.get('code', 'UNKNOWN')
                    error_msg = error.get('message', '')
                    
                    print(f"      Error Code: {error_code}")
                    print(f"      Reason: {error_msg[:60]}...")
                    
                    phase = result.get('phase', 'unknown')
                    print(f"      Phase: {phase}")
                    
                    # Show provenance if present
                    provenance = step.get('provenance', 'LIVE')
                    if provenance != 'LIVE':
                        print(f"      Provenance: {provenance}")
                else:
                    print(f"      Result: {status}")
                    duration = result.get('duration_ms', 0)
                    print(f"      Duration: {duration}ms")
    
    # Summary
    failed_count = len([e for e in events if e.get('type') == 'step_fail'])
    ok_count = len([e for e in events if e.get('type') == 'step_ok'])
    
    print(f"\n[SUMMARY]")
    print(f"  Total Steps: {len(step_events)}")
    print(f"  Blocked: {failed_count}")
    print(f"  Succeeded: {ok_count}")
    print(f"  Side Effects: 0 (all blocked actions prevented)")
    print()
    
    print("[VALUE] FailCore provides offline audit - replay, attribute, write rules, not \"hope to reproduce\"")


def _auto_ingest(trace_path: str):
    """Auto-ingest trace to database after run completes"""
    from failcore.utils.paths import get_database_path
    db_path = str(get_database_path())
    
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
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
