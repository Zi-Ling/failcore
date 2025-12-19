# failcore/cli/show.py
import json
from pathlib import Path
from typing import Dict, List


def show_trace(trace_path: str, *, last: bool = False) -> None:

    path = Path(trace_path)
    if not path.exists():
        print(f"[failcore] trace file not found: {trace_path}")
        return

    events: List[Dict] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[failcore] invalid json line: {line}")
                continue

    if not events:
        print("[failcore] no events found")
        return

    if last:
        last_run_id = events[-1].get("run_id")
        events = [e for e in events if e.get("run_id") == last_run_id]

    print("=== TRACE SUMMARY ===")

    for ev in events:
        etype = ev.get("type") or ev.get("event")
        step_id = ev.get("step_id", "?")
        tool = ev.get("tool", "?")

        if etype == "STEP_START":
            print(f"{step_id} {tool}  START")

        elif etype == "STEP_OK":
            dur = ev.get("duration_ms", "?")
            out = ev.get("output_summary", {})
            val = out.get("value")
            print(f"{step_id} {tool}  OK    {dur}ms  output={val}")

        elif etype == "STEP_FAIL":
            dur = ev.get("duration_ms", "?")
            code = ev.get("error_code", "?")
            msg = ev.get("error_message", "") or ""
            print(f"{step_id} {tool}  FAIL  {dur}ms  {code} {msg}")

        else:
            continue

