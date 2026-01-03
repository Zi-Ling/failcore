# examples/smoke_failcore.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from failcore import Session
from failcore.core.step import StepStatus

# Adjust these imports to match your repo layout if needed
from failcore.core.tools.metadata import ToolMetadata, RiskLevel, SideEffect, DefaultAction
from failcore.core.validate.rules import RuleAssembler
from failcore.core.contract import ExpectedKind


def write_file(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {path}"


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def fetch_url(url: str) -> str:
    # Simulated network tool (no real request)
    return f"Fetched: {url}"


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def load_jsonl(path: Path) -> list[dict]:
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def assert_trace_event_shape(e: Dict[str, Any]) -> None:
    # Minimal v0.1.2 shape checks (adjust if you changed schema)
    assert_true("schema" in e, "trace event missing 'schema'")
    assert_true("seq" in e, "trace event missing 'seq'")
    assert_true("ts" in e, "trace event missing 'ts'")
    assert_true("level" in e, "trace event missing 'level'")
    assert_true("event" in e and isinstance(e["event"], dict), "trace event missing 'event' object")
    assert_true("run" in e and isinstance(e["run"], dict), "trace event missing 'run' object")

    ev = e["event"]
    assert_true("type" in ev, "event missing 'type'")
    # If you standardized these as required in v0.1.2, keep them strict:
    assert_true("severity" in ev, "event missing 'severity' (required by your v0.1.2)")
    assert_true("step" in ev and isinstance(ev["step"], dict), "event missing 'step' object")
    step = ev["step"]
    assert_true("id" in step, "step missing 'id'")
    assert_true("tool" in step, "step missing 'tool'")

    # provenance only exists on STEP_START in your current trace examples; keep it conditional
    if ev["type"] == "STEP_START":
        assert_true("provenance" in step, "STEP_START.step missing 'provenance'")

    if ev["type"] == "STEP_END":
        data = ev.get("data", {})
        result = data.get("result", {})
        assert_true("phase" in result, "STEP_END.data.result missing 'phase'")
        assert_true("status" in result, "STEP_END.data.result missing 'status'")
        # When failed, must have error.code
        if result.get("status") in ("FAIL", "BLOCKED"):
            err = result.get("error", {})
            assert_true("code" in err, "STEP_END failure missing error.code")


def main() -> int:
    root = Path(__file__).resolve().parent
    sandbox_root = root / ".sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)

    trace_path = root / "smoke_trace.jsonl"
    if trace_path.exists():
        trace_path.unlink()

    # ---- Build session ----
    session = Session(trace=str(trace_path), sandbox=str(sandbox_root))

    # ---- Register tools (no builtins) ----
    session.register(
        "write_file",
        write_file,
        metadata=ToolMetadata(
            risk_level=RiskLevel.HIGH,
            side_effect=SideEffect.FS,
            default_action=DefaultAction.BLOCK,
        ),
    )
    session.register(
        "read_file",
        read_file,
        metadata=ToolMetadata(
            risk_level=RiskLevel.MEDIUM,
            side_effect=SideEffect.FS,
            default_action=DefaultAction.ALLOW,
        ),
    )
    session.register(
        "fetch_url",
        fetch_url,
        metadata=ToolMetadata(
            risk_level=RiskLevel.HIGH,
            side_effect=SideEffect.NETWORK,
            default_action=DefaultAction.BLOCK,
        ),
    )

    # ---- Auto-assemble rules from metadata ----
    # If you already wired this inside registry/session, you can remove this block.
    assembler = RuleAssembler(sandbox_root=str(sandbox_root))

    # For write_file: enforce sandbox + contract (text)
    write_metadata = ToolMetadata(
        risk_level=RiskLevel.HIGH,
        side_effect=SideEffect.FS,
        default_action=DefaultAction.BLOCK,
    )
    session.bind_rules(
        "write_file",
        assembler.assemble(
            tool_metadata=write_metadata,
            output_contract={"expected_kind": "TEXT"},
            path_param_names=["path", "file_path", "dst", "output_path"],
        ),
    )

    # For read_file: enforce sandbox for medium+ risk
    read_metadata = ToolMetadata(
        risk_level=RiskLevel.MEDIUM,
        side_effect=SideEffect.FS,
        default_action=DefaultAction.ALLOW,
    )
    session.bind_rules(
        "read_file",
        assembler.assemble(
            tool_metadata=read_metadata,
            output_contract={"expected_kind": "TEXT"},
            path_param_names=["path", "file_path", "src", "input_path"],
        ),
    )

    # For fetch_url: SSRF protection + contract
    fetch_metadata = ToolMetadata(
        risk_level=RiskLevel.HIGH,
        side_effect=SideEffect.NETWORK,
        default_action=DefaultAction.BLOCK,
    )
    session.bind_rules(
        "fetch_url",
        assembler.assemble(
            tool_metadata=fetch_metadata,
            output_contract={"expected_kind": "TEXT"},
            network_allowlist=["api.github.com", "*.openai.com"],
        ),
    )

    # ---- Run cases ----
    print("\n=== Smoke Test: normal write/read ===")
    ok_file = sandbox_root / "ok.txt"
    r1 = session.call("write_file", path=str(ok_file), content="hello")
    print("write_file:", r1.status, getattr(r1, "error", None) and r1.error.error_code)
    assert_true(r1.status == StepStatus.OK, f"write_file should succeed, got: {r1.status}")

    r2 = session.call("read_file", path=str(ok_file))
    print("read_file:", r2.status, getattr(r2, "output", None))
    assert_true(r2.status == StepStatus.OK, f"read_file should succeed, got: {r2.status}")

    print("\n=== Smoke Test: file not found ===")
    r3 = session.call("read_file", path=str(sandbox_root / "missing.txt"))
    print("read_file missing:", r3.status, getattr(r3, "error", None) and r3.error.error_code)
    assert_true(r3.status in (StepStatus.FAIL, "fail"), f"missing read should fail, got: {r3.status}")

    print("\n=== Smoke Test: path traversal blocked ===")
    r4 = session.call("write_file", path=str(sandbox_root / ".." / "escape.txt"), content="hack")
    print("write_file traversal:", r4.status, getattr(r4, "error", None) and r4.error.error_code)
    # v0.1.2: Validation/policy interception returns BLOCKED, not FAIL
    assert_true(r4.status == StepStatus.BLOCKED, f"path traversal must be BLOCKED, got: {r4.status}")
    # Strong expectation:
    if getattr(r4, "error", None):
        assert_true(r4.error.error_code in ("PATH_TRAVERSAL", "SANDBOX_VIOLATION", "POLICY_DENIED"),
                    f"unexpected traversal error code: {r4.error.error_code}")

    print("\n=== Smoke Test: SSRF blocked ===")
    r5 = session.call("fetch_url", url="http://127.0.0.1:8080/admin")
    print("fetch_url ssrf:", r5.status, getattr(r5, "error", None) and r5.error.error_code)
    # v0.1.2: Validation/policy interception returns BLOCKED, not FAIL
    assert_true(r5.status == StepStatus.BLOCKED, f"SSRF must be BLOCKED, got: {r5.status}")

    print("\n=== Trace checks ===")
    assert_true(trace_path.exists(), "trace file not created")
    events = load_jsonl(trace_path)
    assert_true(len(events) > 0, "trace file empty")

    for e in events:
        assert_trace_event_shape(e)

    # quick sanity: should contain at least one STEP_START and STEP_END
    types = [e["event"]["type"] for e in events]
    assert_true("STEP_START" in types, "trace missing STEP_START")
    assert_true("STEP_END" in types, "trace missing STEP_END")

    print("\n[OK] Smoke test passed.")
    print(f"Trace: {trace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
