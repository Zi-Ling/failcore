# failcore/cli/audit_cmd.py
"""
audit command - Generate audit report (audit.jsonl or audit.html) from trace.jsonl

Usage:
- failcore audit
    Generate audit.jsonl for last run (from database -> trace_path)
- failcore audit --trace trace.jsonl
    Generate audit.jsonl from a specific trace file
- failcore audit --trace trace.jsonl --html
    Generate audit.html (document-grade HTML report)
- failcore audit --trace trace.jsonl --out out/audit.jsonl
    Write to explicit path
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from failcore.infra.storage import SQLiteStore
from failcore.core.audit.analyzer import analyze_events
from failcore.infra.audit.writer import write_audit_jsonl
from failcore.cli.views.audit_report import build_audit_view
from failcore.cli.renderers.html import HtmlRenderer


def register_command(subparsers):
    """Register the 'audit' command and its arguments."""
    audit_p = subparsers.add_parser("audit", help="Generate audit report (audit.json)")
    audit_p.add_argument("--trace", help="Path to trace.jsonl file (default: last run)")
    audit_p.add_argument("--out", help="Output path for audit.json (default: <trace_stem>_audit.json)")
    audit_p.add_argument("--pretty", action="store_true", help="Pretty JSON output (indent=2)")
    audit_p.add_argument("--html", action="store_true", help="Generate HTML report instead of JSON")
    audit_p.set_defaults(func=generate_audit)


def generate_audit(args) -> int:
    """
    Generate audit report (audit.jsonl by default, or audit.html with --html).

    Expected args attributes:
      - trace: Optional[str]   path to trace.jsonl
      - out: Optional[str]     output path for audit.jsonl or audit.html
      - pretty: bool           (unused for JSONL, kept for compatibility)
      - html: bool             generate HTML report
    """
    # If trace file is specified, use it directly
    if getattr(args, "trace", None):
        trace_path = Path(args.trace)
        if not trace_path.exists():
            print(f"Error: Trace file not found: {trace_path}")
            return 1
        return _generate_audit_from_trace(
            trace_path,
            out_path=Path(args.out) if getattr(args, "out", None) else None,
            pretty=bool(getattr(args, "pretty", False)),
            html=bool(getattr(args, "html", False)),
        )

    # Otherwise, get the last run from database
    from failcore.utils.paths import get_database_path
    db_path = str(get_database_path())

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Hint: Run 'failcore trace ingest <trace.jsonl>' first")
        return 1

    # Query database for last run
    with SQLiteStore(db_path) as store:
        cursor = store.conn.cursor()
        cursor.execute(
            """
            SELECT run_id, trace_path FROM runs
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
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

        return _generate_audit_from_trace(
            trace_path,
            out_path=Path(args.out) if getattr(args, "out", None) else None,
            pretty=bool(getattr(args, "pretty", False)),
            html=bool(getattr(args, "html", False)),
        )


def _generate_audit_from_trace(
    trace_path: Path,
    *,
    out_path: Optional[Path],
    pretty: bool,
    html: bool,
) -> int:
    """
    Generate audit report from a trace file.

    Output default:
      audit.jsonl (JSONL stream conforming to failcore.audit.v0.1.1 schema)
      OR audit.html (HTML document-grade report)
    """
    try:
        events = _read_trace_jsonl(trace_path)
        report = analyze_events(events, trace_path=str(trace_path))

        if html:
            # HTML output
            view = build_audit_view(report, trace_path=str(trace_path), trace_events=events)
            view.meta.overall_status = "AUDIT"  # Signal to layout.py for audit header
            
            renderer = HtmlRenderer()
            html_content = renderer.render_audit_report(view)

            if out_path is None:
                out_path = trace_path.parent / "audit.html"
            
            out_path.write_text(html_content, encoding='utf-8')
            print(f"[OK] audit HTML report generated: {out_path}")
        else:
            # JSONL output (conforming to failcore.audit.v0.1.1 schema)
            if out_path is None:
                out_path = trace_path.parent / "audit.jsonl"

            # Extract run info from events
            run_info = _extract_run_info(events)
            host_info = _extract_host_info(events)
            
            write_audit_jsonl(
                report, 
                out_path,
                run_info=run_info,
                host_info=host_info
            )
            print(f"[OK] audit (JSONL) generated: {out_path}")

        return 0

    except Exception as e:
        print(f"Error: Failed to generate audit report: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _read_trace_jsonl(trace_path: Path) -> list[dict]:
    """
    Read trace.jsonl (one JSON object per line) into list[dict].

    Notes:
      - Skips empty lines
      - Raises on invalid JSON (fail-fast)
    """
    events: list[dict] = []
    with trace_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                raise ValueError(f"Invalid JSON at {trace_path}:{i}: {e}") from e
            if not isinstance(obj, dict):
                raise ValueError(f"Invalid trace event at {trace_path}:{i}: expected object, got {type(obj)}")
            events.append(obj)
    return events


def _extract_run_info(events: list[dict]) -> Optional[dict]:
    """Extract run metadata from trace events."""
    for evt in events:
        run = evt.get("run")
        if isinstance(run, dict):
            return {
                "run_id": run.get("run_id", "unknown"),
                "created_at": run.get("created_at", ""),
                "workspace": run.get("workspace"),
                "cwd": run.get("cwd"),
                "version": run.get("version", {"spec": "v0.1.1"}),
            }
    return None


def _extract_host_info(events: list[dict]) -> Optional[dict]:
    """Extract host metadata from trace events."""
    for evt in events:
        host = evt.get("host")
        if isinstance(host, dict):
            return {
                "os": host.get("os"),
                "python": host.get("python"),
                "pid": host.get("pid"),
            }
    return None
