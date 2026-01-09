# failcore/cli/commands/proxy_cmd.py
"""
Proxy command - Start FailCore Proxy server

Minimal, production-oriented CLI:
- Binds an ASGI server (uvicorn)
- Wires upstream + pipeline + egress
- Fail-open by default
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from failcore.core.proxy import (
    ProxyConfig,
    ProxyServer,
    ProxyPipeline,
    StreamHandler,
)
from failcore.core.egress import (
    EgressEngine,
    TraceSink,
    UsageEnricher,
    DLPEnricher,
    TaintEnricher,
)


from failcore.core.proxy.upstream import HttpxUpstreamClient

# ----------------------------
# CLI registration
# ----------------------------

def register_command(subparsers):
    parser = subparsers.add_parser(
        "proxy",
        help="Start FailCore Proxy server",
        description=(
            "FailCore Proxy – Execution-time safety proxy for LLM APIs.\n"
            "Provides streaming DLP detection, timeout enforcement, cost limits, and audit tracing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--listen",
        default="127.0.0.1:8000",
        help="Listen address (default: 127.0.0.1:8000)",
    )

    parser.add_argument(
        "--upstream",
        help="Override upstream base URL (optional)",
    )

    parser.add_argument(
        "--mode",
        choices=["warn", "strict"],
        default="warn",
        help=(
            "Security mode:\n"
            "  warn   - Detect and log violations, but continue forwarding responses\n"
            "  strict - Actively block unsafe output and stop further streaming\n"
            "  (default: warn)"
        ),
    )

    parser.add_argument(
        "--trace-dir",
        default=".failcore/proxy",
        help="Directory to store execution traces, audits, and replay data",
    )

    parser.add_argument(
        "--budget",
        type=float,
        help=(
            "Max cost in USD (optional).\n"
            "When exceeded, requests are blocked and recorded in the trace."
        ),
    )

    parser.add_argument(
        "--run-id",
        help="Run ID (optional, auto-generated)",
    )

    parser.set_defaults(func=run_proxy)
    return parser


# ----------------------------
# Main entry
# ----------------------------

def run_proxy(args):
    host, port = parse_listen_address(args.listen)
    strict_mode = (args.mode == "strict")

    # Trace setup using unified path structure
    from failcore.utils.paths import init_run, create_run_directory
    
    # Create proxy run directory: .failcore/runs/<date>/proxy_<HHMMSS>/
    ctx = init_run(command_name="proxy", run_id=args.run_id)
    run_dir = create_run_directory(ctx, exist_ok=True)
    
    run_id = ctx.run_id
    # Unified naming: proxy also uses trace.jsonl (differentiated by run.kind)
    trace_path = run_dir / "trace.jsonl"
    # Create sandbox directory for consistency with run mode
    sandbox_path = run_dir / "sandbox"
    sandbox_path.mkdir(parents=True, exist_ok=True)

    # ---- Minimal startup log (no noise) ----
    # Convert to relative path with forward slashes
    try:
        trace_path_rel = trace_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        trace_path_rel = trace_path.as_posix()
    print(f"[failcore.proxy] listen={host}:{port} mode={args.mode} trace={trace_path_rel}")

    # ---- Egress engine (sync writes = easier debugging) ----
    # TraceSink now wraps EventWriter with v0.1.3 envelope format
    trace_sink = TraceSink(
        str(trace_path),
        async_mode=False,
        buffer_size=1,
        flush_interval_s=0.0,
        run_id=run_id,  # Required for EventWriter
        kind="proxy",  # Mark as proxy run
    )
    egress_engine = EgressEngine(
        trace_sink=trace_sink,
        enrichers=[
            UsageEnricher(),
            DLPEnricher(),
            TaintEnricher(),
        ],
    )

    # ---- Upstream client ----
    upstream_client = HttpxUpstreamClient(
        default_upstream=args.upstream,
        timeout_s=60.0,
        max_retries=0,
    )

    # ---- Proxy core ----
    config = ProxyConfig(
        host=host,
        port=port,
        streaming_strict_mode=strict_mode,
        dlp_strict_mode=strict_mode,
        run_id=run_id,
        budget=args.budget,
    )

    # ---- Create EventWriter for ATTEMPT/RESULT events ----
    from datetime import datetime, timezone
    from failcore.utils.paths import to_failcore_relative
    from failcore.core.trace.writer import EventWriter
    
    # EventWriter handles RUN_START/RUN_END and provides ATTEMPT/RESULT for pipeline
    event_writer = EventWriter(
        trace_path=trace_path,
        run_id=run_id,
        kind="proxy",
        buffer_size=1,
    )
    
    # Write RUN_START event
    event_writer.write_run_event("RUN_START", {
        "mode": args.mode,
        "listen": f"{host}:{port}",
        "sandbox_root": to_failcore_relative(sandbox_path),
    })

    pipeline = ProxyPipeline(
        egress_engine=egress_engine,
        upstream_client=upstream_client,
        event_writer=event_writer,  # Pass EventWriter for ATTEMPT/RESULT
    )

    streaming_handler = StreamHandler(strict_mode=strict_mode)

    server = ProxyServer(
        config=config,
        pipeline=pipeline,
        streaming_handler=streaming_handler,
    )
    
    # ---- Serve ASGI app ----
    try:
        import uvicorn
    except ImportError:
        print(
            "ERROR: uvicorn is required. Install with: pip install uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        uvicorn.run(
            server.app,     # ASGI entry
            host=host,
            port=port,
            log_level="info",
            access_log=False,
        )
    except KeyboardInterrupt:
        print("\n[failcore.proxy] stopped")
    except Exception as e:
        print(f"[failcore.proxy] fatal error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # ---- Write RUN_END event (unified trace envelope) ----
        try:
            event_writer.write_run_event("RUN_END", {})
            event_writer.close()
        except Exception:
            pass
        
        try:
            egress_engine.flush()
            egress_engine.close()
        except Exception:
            pass


# ----------------------------
# Helpers
# ----------------------------

def parse_listen_address(listen: str) -> tuple[str, int]:
    if ":" in listen:
        host, port_str = listen.rsplit(":", 1)
        try:
            return host, int(port_str)
        except ValueError:
            print(f"Invalid port: {port_str}", file=sys.stderr)
            sys.exit(1)
    try:
        return "127.0.0.1", int(listen)
    except ValueError:
        print(f"Invalid listen address: {listen}", file=sys.stderr)
        sys.exit(1)


__all__ = ["register_command"]
