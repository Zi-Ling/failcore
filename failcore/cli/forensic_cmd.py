# failcore/cli/forensic_cmd.py
"""
Forensic command - Generate forensic audit report (audit.json) from trace.jsonl

Usage:
- failcore forensic
    Generate audit.json for last run (from database -> trace_path)
- failcore forensic --trace trace.jsonl
    Generate audit.json from a specific trace file
- failcore forensic --trace trace.jsonl --pretty
    Pretty JSON output
- failcore forensic --trace trace.jsonl --out out/audit.json
    Write to explicit path
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from failcore.infra.storage import SQLiteStore
from failcore.core.forensics.analyzer import analyze_events
from failcore.infra.forensics.writer import write_audit_json
from failcore.cli.views.forensic_report import build_forensic_view
from failcore.cli.renderers.html import HtmlRenderer


def generate_forensic(args) -> int:
    """
    Generate forensic audit report (audit.json).

    Expected args attributes:
      - trace: Optional[str]   path to trace.jsonl
      - out: Optional[str]     output path for audit.json
      - pretty: bool           pretty json
      - html: bool             generate HTML report
    """
    # If trace file is specified, use it directly
    if getattr(args, "trace", None):
        trace_path = Path(args.trace)
        if not trace_path.exists():
            print(f"Error: Trace file not found: {trace_path}")
            return 1
        return _generate_forensic_from_trace(
            trace_path,
            out_path=Path(args.out) if getattr(args, "out", None) else None,
            pretty=bool(getattr(args, "pretty", False)),
            html=bool(getattr(args, "html", False)),
        )

    # Otherwise, get the last run from database
    db_path = ".failcore/failcore.db"

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Hint: Run 'failcore sample' or 'failcore trace ingest <trace.jsonl>' first")
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

        return _generate_forensic_from_trace(
            trace_path,
            out_path=Path(args.out) if getattr(args, "out", None) else None,
            pretty=bool(getattr(args, "pretty", False)),
            html=bool(getattr(args, "html", False)),
        )


def _generate_forensic_from_trace(
    trace_path: Path,
    *,
    out_path: Optional[Path],
    pretty: bool,
    html: bool,
) -> int:
    """
    Generate forensic audit report from a trace file.

    Output default:
      <trace_stem>_audit.json in the same directory as trace.
      OR <trace_stem>_audit.html if html=True
    """
    try:
        events = _read_trace_jsonl(trace_path)
        report = analyze_events(events, trace_path=str(trace_path))

        if html:
            # HTML output
            view = build_forensic_view(report, trace_path=str(trace_path), trace_events=events)
            renderer = HtmlRenderer()
            html_content = renderer.render_forensic_report(view)

            if out_path is None:
                out_path = trace_path.parent / f"{trace_path.stem}_audit.html"
            
            # If user provided .json extension but requested HTML, warn or switch? 
            # For now, trust user provided path if explicit, else use .html default.
            
            out_path.write_text(html_content, encoding='utf-8')
            print(f"✓ Forensic HTML report generated: {out_path}")
        else:
            # JSON output
            if out_path is None:
                out_path = trace_path.parent / f"{trace_path.stem}_audit.json"

            write_audit_json(report, out_path, pretty=pretty)
            print(f"✓ Forensic audit generated: {out_path}")

        return 0

    except Exception as e:
        print(f"Error: Failed to generate forensic audit: {e}")
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
