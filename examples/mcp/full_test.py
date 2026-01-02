"""
FailCore MCP Full Integration Test

Tests the complete MCP integration stack:
- stdio transport (real subprocess)
- JSON-RPC protocol (initialize handshake + tools/list + tools/call)
- FailCore runtime middleware (validation, policy, audit)
- Path security validation (Test 4-6 are CRITICAL security tests)
- Trace writing with detailed events

Key security tests:
- Test 4: Windows absolute path (C:\\Windows\\...)  - MUST be blocked
- Test 5: Unix absolute path (/etc/passwd)        - MUST be blocked
- Test 6: UNC path (\\\\server\\share)               - MUST be blocked
"""

import asyncio
import json
import os
import sys
from pathlib import Path

try:
    from failcore.adapters.mcp.transport import McpTransport, McpTransportConfig
    from failcore.adapters.mcp.session import McpSessionConfig
    from failcore.core.tools.runtime.runtime import ToolRuntime
    from failcore.core.tools.runtime.types import CallContext, ToolEvent
    from failcore.core.tools.runtime.middleware.validation import ValidationMiddleware
    from failcore.core.validate.validator import ValidatorRegistry
    from failcore.core.validate.validators.security import path_traversal_precondition
    from failcore.infra.storage.trace_writer import SyncTraceWriter
except ImportError as e:
    print(f"Error: FailCore not installed. Run: pip install -e .", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    sys.exit(1)


async def test_mcp_integration():
    """Full MCP integration test with real stdio transport + FailCore runtime."""
    
    print("=" * 70)
    print("  FailCore MCP Full Integration Test")
    print("=" * 70)
    print()
    
    # Determine server path
    server_path = Path(__file__).parent / "server.py"
    if not server_path.exists():
        print(f"Error: MCP server not found at {server_path}", file=sys.stderr)
        return 1
    
    # Create trace directory
    from failcore.utils.paths import init_run, create_run_directory, create_sandbox
    run_ctx = init_run(command_name="mcp")
    run_dir = create_run_directory(run_ctx)
    trace_path = run_ctx.trace_path
    
    # Create run-scoped sandbox directory (isolated per run)
    sandbox_abs = create_sandbox(run_ctx)
    
    # CRITICAL: Set environment variable so MCP server uses the same base directory
    os.environ["FAILCORE_SANDBOX_ROOT"] = str(sandbox_abs)
    
    print(f"Server: {server_path}")
    print(f"Trace: {trace_path}")
    print(f"Run ID: {run_ctx.run_id}")
    print(f"Sandbox: {sandbox_abs}")
    print()
    
    # Configure MCP session (stdio transport)
    session_cfg = McpSessionConfig(
        command=[sys.executable, "-u", str(server_path)],
        cwd=None,
        codec_mode="ndjson",
        startup_timeout_s=5.0,
    )
    
    transport_cfg = McpTransportConfig(
        session=session_cfg,
        provider="mcp",
    )
    
    # Initialize MCP transport
    transport = McpTransport(transport_cfg)
    
    # Create validator registry with path security
    validator_registry = ValidatorRegistry()
    
    # Register path traversal validator for MCP tools
    # This is the CRITICAL security layer
    validator_registry.register_precondition(
        "read_text",
        path_traversal_precondition("rel_path", sandbox_root=str(sandbox_abs))
    )
    validator_registry.register_precondition(
        "write_text",
        path_traversal_precondition("rel_path", sandbox_root=str(sandbox_abs))
    )
    
    # Create trace writer (buffered, auto-flush)
    trace_writer = SyncTraceWriter(
        trace_path,
        buffer_size=50,  # Flush every 50 events
        flush_interval_s=0.5,  # Or every 0.5 seconds
    )
    
    # Create middleware stack with validation
    middlewares = [
        ValidationMiddleware(validator_registry=validator_registry),
    ]
    
    # Create ToolRuntime
    runtime = ToolRuntime(
        transport=transport,
        middlewares=middlewares,
        serialize_calls=True,
    )
    
    # Event collector (for trace recording)
    events = []
    
    def emit_and_record(event: ToolEvent):
        events.append(event)
        # Write to trace using TraceWriter (buffered, auto-flush)
        from datetime import datetime
        ts_iso = datetime.fromtimestamp(event.timestamp).isoformat() if event.timestamp else None
        event_dict = {
            "type": "tool_event",
            "run_id": run_ctx.run_id,
            "seq": event.seq,
            "event_type": event.type,
            "message": event.message,
            "data": event.data,
            "timestamp": ts_iso,
        }
        trace_writer.write_event(event_dict)
    
    try:
        # Discover tools
        print("-" * 70)
        print("Phase 1: Tool Discovery (MCP tools/list)")
        print("-" * 70)
        
        tools = await transport.list_tools()
        print(f"Discovered {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name} (provider={tool.provider})")
        print()
        
        # Create test sandbox file (directly in sandbox root)
        test_file = sandbox_abs / "hello.txt"
        test_file.write_text("Hello from FailCore MCP test", encoding="utf-8")
        
        # Test suite
        test_cases = [
            ("Test 1: Safe Read", "read_text", {"rel_path": "hello.txt"}, True),
            ("Test 2: Unix Path Traversal", "read_text", {"rel_path": "../../../etc/passwd"}, False),
            ("Test 3: Windows Path Traversal", "read_text", {"rel_path": "..\\..\\..\\Windows\\win.ini"}, False),
            ("Test 4: Absolute Path (Windows)", "read_text", {"rel_path": "C:\\Windows\\System32\\drivers\\etc\\hosts"}, False),
            ("Test 5: Absolute Path (Unix)", "read_text", {"rel_path": "/etc/passwd"}, False),
            ("Test 6: UNC Path", "read_text", {"rel_path": "\\\\suspicious-server\\c$\\Windows"}, False),
            ("Test 7: Safe Write", "write_text", {"rel_path": "output.txt", "content": "Test write"}, True),
            # Windows-specific attack vectors
            ("Test 8: NT Path Prefix", "read_text", {"rel_path": "\\\\?\\C:\\Windows\\win.ini"}, False),
            ("Test 9: Device Path", "read_text", {"rel_path": "\\\\.\\GLOBALROOT\\Device\\HarddiskVolume1"}, False),
            ("Test 10: Mixed Separators", "read_text", {"rel_path": "subdir/..\\..\\..\\etc\\passwd"}, False),
            ("Test 11: Trailing Dots", "read_text", {"rel_path": "hello.txt..."}, False),
            ("Test 12: Trailing Spaces", "read_text", {"rel_path": "hello.txt   "}, False),
        ]
        
        # Add Windows-specific ADS test
        if sys.platform == 'win32':
            test_cases.append(
                ("Test 13: Alternate Data Stream", "read_text", {"rel_path": "hello.txt:evil_stream"}, False)
            )
        
        for idx, (test_name, tool_name, args, should_succeed) in enumerate(test_cases, 1):
            print("-" * 70)
            print(test_name)
            print("-" * 70)
            
            # Find tool ref
            tool_ref = next((t for t in tools if t.name == tool_name), None)
            if not tool_ref:
                print(f"⚠ Tool '{tool_name}' not found, skipping")
                print()
                continue
            
            # Create call context (CallContext only accepts run_id and trace_id)
            ctx = CallContext(
                run_id=run_ctx.run_id,
                trace_id=run_ctx.run_id,
            )
            
            # Call tool through runtime
            events.clear()
            result = await runtime.call(
                tool=tool_ref,
                args=args,
                ctx=ctx,
                emit=emit_and_record,
            )
            
            # Display result
            print(f"Tool: {tool_name}")
            print(f"Args: {json.dumps(args, ensure_ascii=False)}")
            print(f"Result: ok={result.ok}")
            
            if result.ok:
                content_preview = str(result.content)[:100] if result.content else "N/A"
                print(f"Content: {content_preview}...")
                if should_succeed:
                    print("✓ Test passed (success expected)")
                else:
                    print("⚠ SECURITY GAP: Attack NOT blocked!")
            else:
                error_type = result.error.get("type", "UNKNOWN") if result.error else "UNKNOWN"
                error_code = result.error.get("error_code", "UNKNOWN") if result.error else "UNKNOWN"
                error_msg = result.error.get("message", "Unknown error") if result.error else "Unknown error"
                error_details = result.error.get("details", {}) if result.error else {}
                retryable = result.error.get("retryable", False) if result.error else False
                
                print(f"Error Type: {error_type}")
                print(f"Error Code: {error_code}")
                print(f"Message: {error_msg}")
                print(f"Retryable: {retryable}")
                if error_details:
                    print(f"Details: {json.dumps(error_details, indent=2, ensure_ascii=False)}")
                if not should_succeed:
                    print("✓ Attack blocked (as expected)")
                else:
                    print("✗ Test failed (should have succeeded)")
            
            print(f"Events: {len(events)} emitted")
            print()
        
        # === CRITICAL: Symlink/Junction escape tests ===
        print("=" * 70)
        print("  Advanced Security Tests: Symlink/Junction Escape")
        print("=" * 70)
        print()
        
        # Test: Symlink pointing outside sandbox (Unix/Linux/macOS)
        if sys.platform != 'win32':
            try:
                symlink_path = sandbox_abs / "escape_link"
                symlink_path.symlink_to("/etc")  # Points to /etc
                
                print("-" * 70)
                print("Test: Symlink Escape Attack (Unix)")
                print("-" * 70)
                print(f"Created symlink: {symlink_path} -> /etc")
                
                tool_ref = next((t for t in tools if t.name == "read_text"), None)
                if tool_ref:
                    ctx = CallContext(run_id=run_ctx.run_id, trace_id=run_ctx.run_id)
                    events.clear()
                    result = await runtime.call(
                        tool=tool_ref,
                        args={"rel_path": "escape_link/passwd"},
                        ctx=ctx,
                        emit=emit_and_record,
                    )
                    
                    if result.ok:
                        print("⚠ CRITICAL SECURITY GAP: Symlink escape NOT blocked!")
                        print(f"Content preview: {str(result.content)[:100]}...")
                    else:
                        error_type = result.error.get("type", "UNKNOWN") if result.error else "UNKNOWN"
                        error_code = result.error.get("error_code", "UNKNOWN") if result.error else "UNKNOWN"
                        print(f"Error Type: {error_type}")
                        print(f"Error Code: {error_code}")
                        print("✓ Symlink escape blocked (as expected)")
                    print()
                
                # Cleanup
                symlink_path.unlink()
            except Exception as e:
                print(f"⚠ Symlink test skipped: {e}")
                print()
        
        # Test: Junction pointing outside sandbox (Windows)
        if sys.platform == 'win32':
            try:
                import subprocess
                junction_path = sandbox_abs / "escape_junction"
                
                # Create junction using mklink (requires admin on older Windows)
                result_code = subprocess.call(
                    ["cmd", "/c", "mklink", "/J", str(junction_path), "C:\\Windows"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                if result_code == 0:
                    print("-" * 70)
                    print("Test: Junction Escape Attack (Windows)")
                    print("-" * 70)
                    print(f"Created junction: {junction_path} -> C:\\Windows")
                    
                    tool_ref = next((t for t in tools if t.name == "read_text"), None)
                    if tool_ref:
                        ctx = CallContext(run_id=run_ctx.run_id, trace_id=run_ctx.run_id)
                        events.clear()
                        result = await runtime.call(
                            tool=tool_ref,
                            args={"rel_path": "escape_junction\\win.ini"},
                            ctx=ctx,
                            emit=emit_and_record,
                        )
                        
                        if result.ok:
                            print("⚠ CRITICAL SECURITY GAP: Junction escape NOT blocked!")
                            print(f"Content preview: {str(result.content)[:100]}...")
                        else:
                            error_type = result.error.get("type", "UNKNOWN") if result.error else "UNKNOWN"
                            error_code = result.error.get("error_code", "UNKNOWN") if result.error else "UNKNOWN"
                            print(f"Error Type: {error_type}")
                            print(f"Error Code: {error_code}")
                            print("✓ Junction escape blocked (as expected)")
                        print()
                    
                    # Cleanup
                    junction_path.rmdir()
                else:
                    print("⚠ Junction test skipped (requires admin privileges on some Windows versions)")
                    print()
            except Exception as e:
                print(f"⚠ Junction test skipped: {e}")
                print()
        
    finally:
        await transport.shutdown()
        trace_writer.close()  # Ensure all events are flushed
    
    print("=" * 70)
    print("  Test Complete")
    print("=" * 70)
    print(f"\nTrace saved to: {trace_path}")
    print(f"\nView commands:")
    print(f"  failcore show {trace_path}")
    print(f"  failcore audit {trace_path}")
    print(f"  failcore report {trace_path}")
    
    return 0


if __name__ == "__main__":
    # Windows compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        exit_code = asyncio.run(test_mcp_integration())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[TEST] Interrupted by user", file=sys.stderr)
        sys.exit(130)
