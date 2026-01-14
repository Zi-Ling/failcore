from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Protocol

from .base import Middleware
from ..types import CallContext, Receipt, ToolResult, ToolSpecRef


class AuditSink(Protocol):
    """
    A sink that accepts structured audit records.
    Implementations can write to file, stdout, database, etc.
    """

    def write(self, record: Dict[str, Any]) -> None: ...


class JsonlFileAuditSink:
    """
    Append-only JSONL sink.
    Each record is written as one JSON object per line.
    Thread-safe for simple usage (runtime is typically async, but file writes are sync).
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def write(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


def _json_safe(obj: Any) -> Any:
    """
    Best-effort conversion to JSON-safe structures.
    - dataclass -> dict
    - unknown -> repr(...)
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    # fallback
    return repr(obj)


def _receipts_to_json(receipts: list[Receipt]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in receipts:
        out.append({"kind": r.kind, "data": _json_safe(r.data)})
    return out


class AuditMiddleware(Middleware):
    """
    Execution-time auditing middleware.

    It records a compact, structured audit trail:
    - call_start
    - call_success (includes short-circuit info via result payload hints)
    - call_error

    Notes:
    - By default, it does NOT include ToolResult.raw (debug-only boundary).
    - Records are JSONL-friendly.
    """

    def __init__(
        self,
        sink: AuditSink,
        *,
        include_args: bool = True,
        include_content: bool = True,
        include_raw: bool = False,
        include_receipts: bool = True,
        max_value_chars: int = 20_000,
    ) -> None:
        self._sink = sink
        self._include_args = include_args
        self._include_content = include_content
        self._include_raw = include_raw
        self._include_receipts = include_receipts
        self._max_value_chars = max_value_chars

        # middleware-local sequence to order audit records emitted by this middleware
        self._audit_seq = 0
        self._lock = threading.Lock()

    def _next_audit_seq(self) -> int:
        with self._lock:
            self._audit_seq += 1
            return self._audit_seq

    def _truncate(self, v: Any) -> Any:
        """
        Prevent extremely large payloads from bloating audit logs.
        """
        s = None
        try:
            s = json.dumps(_json_safe(v), ensure_ascii=False)
        except Exception:
            s = repr(v)
        if s is None:
            return None
        if len(s) <= self._max_value_chars:
            try:
                return json.loads(s)
            except Exception:
                return s
        # truncated
        head = s[: self._max_value_chars]
        return {"__truncated__": True, "head": head, "total_chars": len(s)}

    def _base_record(self, kind: str, tool: ToolSpecRef, ctx: CallContext) -> Dict[str, Any]:
        return {
            "schema": "failcore.audit.v0.1",
            "kind": kind,  # call_start | call_success | call_error
            "ts": time.time(),
            "audit_seq": self._next_audit_seq(),
            "run_id": ctx.run_id,
            "trace_id": ctx.trace_id,
            "replay_id": ctx.replay_id,
            "tool": {
                "name": tool.name,
                "provider": tool.provider,
                "version": tool.version,
            },
            "ctx": {
                "start_time": ctx.start_time,
                "metadata": dict(ctx.metadata),
            },
        }

    async def on_call_start(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        emit,
    ) -> Optional[ToolResult]:
        rec = self._base_record("call_start", tool, ctx)
        if self._include_args:
            rec["args"] = self._truncate(args)
        self._sink.write(rec)
        return None

    async def on_call_success(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        result: ToolResult,
        emit,
    ) -> None:
        rec = self._base_record("call_success", tool, ctx)
        rec["duration_ms"] = int((time.time() - ctx.start_time) * 1000)
        rec["ok"] = bool(result.ok)

        if self._include_content:
            rec["content"] = self._truncate(result.content)

        # raw is debug-only; disabled by default
        if self._include_raw:
            rec["raw"] = self._truncate(result.raw)

        if result.error is not None:
            rec["error"] = self._truncate(result.error)

        if self._include_receipts:
            rec["receipts"] = _receipts_to_json(result.receipts)

        if result.usage is not None:
            rec["usage"] = self._truncate(result.usage)

        self._sink.write(rec)
        return None

    async def on_call_error(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        error: Exception,
        emit,
    ) -> None:
        rec = self._base_record("call_error", tool, ctx)
        rec["duration_ms"] = int((time.time() - ctx.start_time) * 1000)
        rec["ok"] = False
        rec["error"] = {
            "type": error.__class__.__name__,
            "message": str(error),
        }
        self._sink.write(rec)
        return None
