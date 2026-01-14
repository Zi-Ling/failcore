# failcore/cli/commands/run_cmd.py
"""
Run command - Execute adapter under FailCore runtime

Design:
- Managed mode (recommended):
    failcore run mcp <target> [args...]
  FailCore owns how to launch the server (interpreter selection, -u, etc.)

- Passthrough mode (escape hatch):
    failcore run mcp -- <cmd> [args...]
  FailCore does NOT modify the command (user owns launch details).
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from failcore.utils import get_trace_path


def register_command(subparsers):
    """Register the 'run' command."""
    run_p = subparsers.add_parser("run", help="Run adapter under FailCore runtime")
    run_p.add_argument("adapter", choices=["mcp"], help="Adapter type")

    # We parse tokens after adapter ourselves to support:
    #   failcore run mcp xxx.py [args...]
    #   failcore run mcp -- python -u xxx.py [args...]
    run_p.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="Managed: <target> [args...] | Passthrough: -- <cmd> [args...]",
    )

    run_p.add_argument("--cwd", help="Working directory for the server process")
    run_p.add_argument("--trace", help="Trace output path (default: .failcore/runs/<date>/<run_id>_<HHMMSS>_mcp/trace.jsonl)")
    run_p.add_argument("--startup-timeout", type=float, default=None, help="Override MCP startup timeout (seconds)")
    run_p.add_argument("--with-hooks", action="store_true", help="Enable all hooks (httpx/requests/subprocess/os)")
    run_p.set_defaults(func=run_adapter)


def run_adapter(args):
    """Dispatch to adapter-specific implementation."""
    # Enable hooks if requested
    if args.with_hooks:
        _enable_hooks()
    
    try:
        if args.adapter == "mcp":
            return asyncio.run(_run_mcp(args))
    finally:
        # Clean up hooks
        if args.with_hooks:
            _disable_hooks()


def _enable_hooks():
    """Enable all hooks with egress engine"""
    from failcore.hooks import enable_all_hooks
    from failcore.core.egress import EgressEngine, TraceSink, UsageEnricher, DLPEnricher, TaintEnricher
    from pathlib import Path
    import time
    
    # Create egress engine for hooks
    trace_dir = Path(".failcore/hooks")
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"hooks_{int(time.time())}.jsonl"
    
    trace_sink = TraceSink(trace_path, async_mode=True)
    enrichers = [UsageEnricher(), DLPEnricher(), TaintEnricher()]
    egress_engine = EgressEngine(trace_sink=trace_sink, enrichers=enrichers)
    
    enable_all_hooks(egress_engine)
    print(f"✓ Hooks enabled (trace: {trace_path})")


def _disable_hooks():
    """Disable all hooks"""
    from failcore.hooks import disable_all_hooks
    disable_all_hooks()
    print("✓ Hooks disabled")
    print(f"Error: Adapter '{args.adapter}' not implemented", file=sys.stderr)
    return 1


def _is_probably_path(s: str) -> bool:
    # If it contains a path separator or ends with a known file suffix, treat it like a path.
    lowered = s.lower()
    return ("/" in s) or ("\\" in s) or lowered.endswith((".py", ".js", ".mjs", ".cjs", ".exe", ".cmd", ".bat"))


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _normalize_managed_command(target: str, target_args: List[str]) -> List[str]:
    """
    Managed mode:
    - If target is a .py file: run with sys.executable -u
    - .js/.mjs/.cjs: run with node
    - .cmd/.bat: run with cmd /c
    - .exe or other: run directly
    - If target is not a path and exists on PATH, run it directly (no exists() check).
    """
    p = Path(target)

    # PATH command (no separators, no obvious suffix) → allow directly if exists
    if not _is_probably_path(target):
        resolved = _which(target)
        if resolved:
            return [resolved, *target_args]
        # fall through: might still be a relative path without separators (rare)

    # Path-like: if it looks like a path, ensure it exists
    if _is_probably_path(target):
        if not p.exists():
            raise FileNotFoundError(f"Target not found: {target}")
        abs_target = str(p.resolve())
        suffix = p.suffix.lower()
    else:
        # treat as path anyway
        abs_target = str(p.resolve())
        suffix = p.suffix.lower()

    if suffix == ".py":
        # Force unbuffered stdio for MCP/stdio correctness
        return [sys.executable, "-u", abs_target, *target_args]

    if suffix in (".js", ".mjs", ".cjs"):
        node = _which("node") or "node"
        return [node, abs_target, *target_args]

    if suffix in (".cmd", ".bat"):
        # Windows batch scripts must run under cmd.exe
        return ["cmd", "/c", abs_target, *target_args]

    # .exe or other executable / script file
    return [abs_target, *target_args]


def _parse_run_rest(rest: List[str]) -> tuple[str, List[str], str]:
    """
    Return (mode, command, mode_note)

    - Passthrough: rest starts with '--'  -> command = rest[1:]
    - Managed:     rest otherwise         -> target = rest[0], args = rest[1:]
    """
    if not rest:
        raise ValueError("Missing target. Usage: failcore run mcp <target> [args...] OR failcore run mcp -- <cmd> [args...]")

    # Argparse REMAINDER may include the literal "--" or may omit it depending on how it's invoked,
    # but in practice it WILL include it for our pattern. We handle both.
    if rest[0] == "--":
        cmd = rest[1:]
        if not cmd:
            raise ValueError("Passthrough mode requires a command after '--'. Example: failcore run mcp -- python -u server.py")
        return ("passthrough", cmd, "User owns launch command (no auto -u / no interpreter selection).")

    # Some shells/argparse variants may not keep '--' in REMAINDER; support common pattern:
    # failcore run mcp --python ... (we intentionally do NOT support this style)
    if rest[0].startswith("--"):
        # Avoid silently treating options as a target; give a helpful error.
        raise ValueError(
            f"Unexpected option '{rest[0]}' before target.\n"
            "Use managed mode:  failcore run mcp <target> [args...]\n"
            "Or passthrough:    failcore run mcp -- <cmd> [args...]"
        )

    target = rest[0]
    target_args = rest[1:]
    cmd = _normalize_managed_command(target, target_args)
    return ("managed", cmd, "FailCore owns launch command (auto interpreter + -u for .py).")


async def _run_mcp(args):
    """Run MCP adapter with managed or passthrough mode."""
    from failcore.infra.transports.mcp import McpTransport, McpTransportConfig
    from failcore.infra.transports.mcp.session import McpSessionConfig

    try:
        mode, command, mode_note = _parse_run_rest(args.rest)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Working directory
    cwd = args.cwd
    if cwd:
        cwd = str(Path(cwd).resolve())
    else:
        cwd = None

    # Use unified trace path generation
    trace_path = get_trace_path(command_name="mcp", custom_path=args.trace)

    # Session config
    session_kwargs = dict(
        command=command,
        cwd=cwd,
        codec_mode="ndjson",
    )
    if args.startup_timeout is not None:
        session_kwargs["startup_timeout_s"] = args.startup_timeout

    session_cfg = McpSessionConfig(**session_kwargs)

    transport_cfg = McpTransportConfig(
        session=session_cfg,
        provider="mcp",
    )

    transport = McpTransport(transport_cfg)

    print(f"[RUN:MCP:{mode.upper()}]", file=sys.stderr)
    print(f"  Command: {' '.join(command)}", file=sys.stderr)
    print(f"  CWD: {cwd or '(default)'}", file=sys.stderr)
    print(f"  Trace: {trace_path}", file=sys.stderr)
    print(f"  Note: {mode_note}", file=sys.stderr)
    if mode == "passthrough":
        if command and (Path(command[0]).name.lower().startswith("python") or command[0].lower().endswith("python.exe")):
            if "-u" not in command:
                print("  Tip: For Python stdio servers, consider adding '-u' to avoid stdout buffering.", file=sys.stderr)
    print(file=sys.stderr)

    try:
        tools = await transport.list_tools()
        print(f"[RUN:MCP] Available tools: {len(tools)}", file=sys.stderr)
        for tool in tools:
            print(f"  - {tool.name}", file=sys.stderr)
        print("\n[RUN:MCP] Ready. Press Ctrl+C to exit.", file=sys.stderr)

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n[RUN:MCP] Shutting down...", file=sys.stderr)

    except Exception as e:
        print(f"[RUN:MCP] Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1

    finally:
        await transport.shutdown()
        print("[RUN:MCP] Shutdown complete", file=sys.stderr)

    return 0
