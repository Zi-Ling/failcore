# failcore/core/trace/builder.py
"""
Helper functions to build trace events following v0.1.1 spec
"""

from __future__ import annotations
import sys
import os
import hashlib
from typing import Any, Dict, Optional
from .events import (
    TraceEvent,
    EventType,
    LogLevel,
    StepStatus,
    ExecutionPhase,
    StepInfo,
    PayloadInfo,
    ResultInfo,
    PolicyInfo,
    ValidationInfo,
    NormalizeInfo,
    utc_now_iso,
)

# Version constants
SCHEMA_VERSION = "failcore.trace.v0.1.1"
FAILCORE_VERSION = "0.1.0a1"


def _get_host_info() -> Dict[str, Any]:
    """Get host/process information"""
    return {
        "os": sys.platform,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "pid": os.getpid(),
    }


def _hash_value(value: Any) -> str:
    """Generate SHA256 hash of a value"""
    import json
    try:
        s = json.dumps(value, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(s.encode()).hexdigest()[:16]}"
    except:
        return f"sha256:{hashlib.sha256(str(value).encode()).hexdigest()[:16]}"


def build_run_context(
    run_id: str,
    created_at: str,
    workspace: Optional[str] = None,
    sandbox_root: Optional[str] = None,
    cwd: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    flags: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build run context object"""
    ctx = {
        "run_id": run_id,
        "created_at": created_at,
    }
    
    if workspace:
        ctx["workspace"] = workspace
    if sandbox_root:
        ctx["sandbox_root"] = sandbox_root
    if cwd:
        ctx["cwd"] = cwd
    if tags:
        ctx["tags"] = tags
    if flags:
        ctx["flags"] = flags
    
    ctx["version"] = {
        "failcore": FAILCORE_VERSION,
        "spec": "0.1.1",
    }
    
    return ctx


def build_run_start_event(
    seq: int,
    run_id: str,
    created_at: str,
    workspace: Optional[str] = None,
    sandbox_root: Optional[str] = None,
    cwd: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    flags: Optional[Dict[str, Any]] = None,
) -> TraceEvent:
    """Build RUN_START event"""
    run_ctx = build_run_context(
        run_id=run_id,
        created_at=created_at,
        workspace=workspace,
        sandbox_root=sandbox_root,
        cwd=cwd,
        tags=tags,
        flags=flags,
    )
    
    return TraceEvent(
        schema=SCHEMA_VERSION,
        seq=seq,
        ts=utc_now_iso(),
        level=LogLevel.INFO,
        event={
            "type": EventType.RUN_START.value,
            "data": {},
        },
        run=run_ctx,
        host=_get_host_info(),
        actor={"type": "system", "name": "failcore"},
        security={"payload_mode": "summary"},
    )


def build_step_start_event(
    seq: int,
    run_context: Dict[str, Any],
    step_id: str,
    tool: str,
    params: Dict[str, Any],
    attempt: int = 1,
    depends_on: Optional[list] = None,
) -> TraceEvent:
    """Build STEP_START event"""
    # Build fingerprint
    fingerprint = {
        "id": f"fp_{run_context['run_id']}_{step_id}",
        "algo": "sha256",
        "scope": "tool+params+run_context",
        "inputs": {
            "tool": tool,
            "params_hash": _hash_value(params),
            "context_hash": _hash_value({"run_id": run_context["run_id"]}),
        }
    }
    
    step_info = {
        "id": step_id,
        "tool": tool,
        "attempt": attempt,
        "depends_on": depends_on or [],
        "fingerprint": fingerprint,
    }
    
    # Build payload
    payload = {
        "input": {
            "mode": "summary",
            "summary": params,
            "hash": _hash_value(params),
        }
    }
    
    return TraceEvent(
        schema=SCHEMA_VERSION,
        seq=seq,
        ts=utc_now_iso(),
        level=LogLevel.INFO,
        event={
            "type": EventType.STEP_START.value,
            "step": step_info,
            "data": {"payload": payload},
        },
        run={"run_id": run_context["run_id"], "created_at": run_context["created_at"]},
    )


def build_policy_denied_event(
    seq: int,
    run_context: Dict[str, Any],
    step_id: str,
    tool: str,
    attempt: int,
    policy_id: str,
    rule_id: str,
    rule_name: str,
    reason: str,
) -> TraceEvent:
    """Build POLICY_DENIED event"""
    return TraceEvent(
        schema=SCHEMA_VERSION,
        seq=seq,
        ts=utc_now_iso(),
        level=LogLevel.WARN,
        event={
            "type": EventType.POLICY_DENIED.value,
            "step": {"id": step_id, "tool": tool, "attempt": attempt},
            "data": {
                "policy": {
                    "policy_id": policy_id,
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "decision": "deny",
                    "reason": reason,
                    "action_taken": "halt",
                    "matched_rules": [rule_id],
                }
            },
        },
        run={"run_id": run_context["run_id"], "created_at": run_context["created_at"]},
    )


def build_output_normalized_event(
    seq: int,
    run_context: Dict[str, Any],
    step_id: str,
    tool: str,
    attempt: int,
    expected_kind: Optional[str],
    observed_kind: str,
    reason: Optional[str] = None,
) -> TraceEvent:
    """Build OUTPUT_NORMALIZED event"""
    decision = "mismatch" if expected_kind and expected_kind != observed_kind else "ok"
    
    return TraceEvent(
        schema=SCHEMA_VERSION,
        seq=seq,
        ts=utc_now_iso(),
        level=LogLevel.WARN if decision == "mismatch" else LogLevel.INFO,
        event={
            "type": EventType.OUTPUT_NORMALIZED.value,
            "step": {"id": step_id, "tool": tool, "attempt": attempt},
            "data": {
                "normalize": {
                    "expected_kind": expected_kind,
                    "observed_kind": observed_kind,
                    "decision": decision,
                    "reason": reason or "",
                    "strategy": "keep_original_type",
                }
            },
        },
        run={"run_id": run_context["run_id"], "created_at": run_context["created_at"]},
    )


def build_step_end_event(
    seq: int,
    run_context: Dict[str, Any],
    step_id: str,
    tool: str,
    attempt: int,
    status: StepStatus,
    phase: ExecutionPhase,
    duration_ms: int,
    output: Optional[Any] = None,
    error: Optional[Dict[str, Any]] = None,
    warnings: Optional[list] = None,
) -> TraceEvent:
    """Build STEP_END event"""
    result = {
        "status": status.value,
        "phase": phase.value,
        "duration_ms": duration_ms,
    }
    
    if error:
        result["error"] = error
    if warnings:
        result["warnings"] = warnings
    
    event_data = {"result": result}
    
    # Add output payload if present
    if output:
        event_data["payload"] = {
            "output": {
                "mode": "summary",
                "kind": output.get("kind", "unknown"),
                "summary": output.get("value"),
                "hash": _hash_value(output.get("value")),
            }
        }
    
    return TraceEvent(
        schema=SCHEMA_VERSION,
        seq=seq,
        ts=utc_now_iso(),
        level=LogLevel.INFO if status == StepStatus.OK else LogLevel.ERROR,
        event={
            "type": EventType.STEP_END.value,
            "step": {"id": step_id, "tool": tool, "attempt": attempt},
            "data": event_data,
        },
        run={"run_id": run_context["run_id"], "created_at": run_context["created_at"]},
    )


def build_run_end_event(
    seq: int,
    run_context: Dict[str, Any],
    summary: Dict[str, Any],
) -> TraceEvent:
    """Build RUN_END event"""
    return TraceEvent(
        schema=SCHEMA_VERSION,
        seq=seq,
        ts=utc_now_iso(),
        level=LogLevel.INFO,
        event={
            "type": EventType.RUN_END.value,
            "data": {"summary": summary},
        },
        run={"run_id": run_context["run_id"], "created_at": run_context["created_at"]},
    )
