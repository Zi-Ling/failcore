from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from failcore.core.tools.runtime.transports.base import BaseTransport, EventEmitter
from failcore.core.tools.runtime.types import CallContext, Receipt, ToolEvent, ToolResult, ToolSpecRef

from .session import McpSession, McpSessionConfig, McpSessionError


@dataclass
class McpTransportConfig:
    """
    MCP transport config.

    Methods are configurable because MCP servers/adapters may differ.

    Required RPCs:
      - list_tools_method: returns tool list
      - call_tool_method: calls tool with {name, arguments}

    Optional notifications (server -> client, JSON-RPC without "id"):
      - progress_method: treated as progress events
      - log_method: treated as log events
      - partial_method: treated as partial events
      - generic_event_method: treated as generic event envelope
    """

    session: McpSessionConfig

    list_tools_method: str = "tools/list"
    call_tool_method: str = "tools/call"

    # Provider name to set into ToolSpecRef
    provider: str = "mcp"
    server_version: Optional[str] = None

    # Notification method names (best-effort defaults)
    progress_method: str = "progress"
    log_method: str = "log"
    partial_method: str = "partial"
    generic_event_method: str = "event"


class McpTransport(BaseTransport):
    """
    MCP transport implementation backed by a long-lived stdio session.

    Streaming:
      - Supports true server notifications via McpSession(on_notification=...).
      - Also supports "events bundled in final result" as a fallback.

    Concurrency note:
      - ToolRuntime defaults to serialize calls.
      - McpSession defaults to serialize_requests=True.
      - We still guard notifications with an active emit pointer.
    """

    def __init__(self, cfg: McpTransportConfig) -> None:
        self._cfg = cfg

        # Active emitter for the *current* call (set in call(), cleared in finally)
        self._active_emit: Optional[EventEmitter] = None

        # Protect _active_emit changes (defensive; runtime is serialized anyway)
        self._emit_lock = asyncio.Lock()

        self._session = McpSession(cfg.session, on_notification=self._on_notification)

    async def shutdown(self) -> None:
        await self._session.shutdown()

    async def list_tools(self, *, ctx: Optional[CallContext] = None) -> list[ToolSpecRef]:
        await self._session.start()

        try:
            res = await self._session.call(self._cfg.list_tools_method, params={})
        except Exception as e:
            raise McpSessionError(f"mcp list_tools failed: {e}") from e

        tools = _extract_tools_list(res)
        out: list[ToolSpecRef] = []
        for t in tools:
            name = t.get("name")
            if not name:
                continue
            out.append(
                ToolSpecRef(
                    name=name,
                    provider=self._cfg.provider,
                    version=self._cfg.server_version,
                )
            )
        return out

    async def call(
        self,
        *,
        tool: ToolSpecRef,
        args: Dict[str, Any],
        ctx: CallContext,
        emit: EventEmitter,
    ) -> ToolResult:
        await self._session.start()

        # Set active emitter so notifications can be forwarded during this call
        async with self._emit_lock:
            self._active_emit = emit

        try:
            emit(ToolEvent(seq=0, type="progress", message="mcp rpc send", data={"tool": tool.name}))

            params = {"name": tool.name, "arguments": args or {}}

            try:
                raw = await self._session.call(self._cfg.call_tool_method, params=params)
            except Exception as e:
                return ToolResult(
                    ok=False,
                    content=None,
                    raw=None,
                    error={"type": e.__class__.__name__, "message": str(e)},
                )

            # Fallback: some servers bundle events in final response
            _emit_bundled_events(emit, raw)

            ok, content, err = _normalize_call_result(raw)
            receipts = _extract_receipts(raw)

            emit(
                ToolEvent(
                    seq=0,
                    type="progress",
                    message="mcp rpc received",
                    data={"tool": tool.name, "ok": ok},
                )
            )

            return ToolResult(
                ok=ok,
                content=content,
                raw=raw,  # debug-only boundary; middleware controls persistence
                error=err,
                receipts=receipts,
            )

        finally:
            async with self._emit_lock:
                self._active_emit = None

    # =========================================================
    # Notifications (true streaming)
    # =========================================================

    async def _on_notification(self, msg: dict[str, Any]) -> None:
        """
        Handle server->client JSON-RPC notifications (no 'id').

        Expected msg shape (JSON-RPC 2.0):
          {"jsonrpc":"2.0","method":"progress","params":{...}}

        We map methods to ToolEvent types.
        """
        method = msg.get("method")
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

        async with self._emit_lock:
            emit = self._active_emit

        if emit is None:
            # No active tool call; ignore to avoid cross-call contamination
            return

        # Common fields
        message = None
        data: Any = None

        if isinstance(params, dict):
            message = params.get("message") or params.get("text")
            data = params.get("data") if "data" in params else params

        # Map notification method to ToolEventType
        etype = "log"
        if method == self._cfg.progress_method:
            etype = "progress"
        elif method == self._cfg.log_method:
            etype = "log"
        elif method == self._cfg.partial_method:
            etype = "partial"
        elif method == self._cfg.generic_event_method:
            # Generic envelope: params may include explicit type
            hinted = params.get("type") if isinstance(params, dict) else None
            if hinted in ("progress", "log", "partial"):
                etype = hinted  # trust
            else:
                etype = "log"

        emit(
            ToolEvent(
                seq=0,
                type=etype,  # runtime will assign seq/correlation
                message=message,
                data=data,
            )
        )


# =========================================================
# Helpers (best-effort normalization)
# =========================================================

def _extract_tools_list(res: Any) -> List[Dict[str, Any]]:
    """
    Best-effort parsing of MCP list_tools result.

    Common shapes:
      - {"tools": [ ... ]}
      - {"result": {"tools": [ ... ]}}
      - [ ... ]
    """
    if isinstance(res, dict):
        if "tools" in res and isinstance(res["tools"], list):
            return [t for t in res["tools"] if isinstance(t, dict)]
        if "result" in res and isinstance(res["result"], dict):
            r = res["result"]
            if "tools" in r and isinstance(r["tools"], list):
                return [t for t in r["tools"] if isinstance(t, dict)]
    if isinstance(res, list):
        return [t for t in res if isinstance(t, dict)]
    return []


def _normalize_call_result(raw: Any) -> tuple[bool, Optional[Any], Optional[Dict[str, Any]]]:
    """
    Normalize MCP call_tool result to (ok, content, error) best-effort.

    Common shapes:
      - {"content": ...}
      - {"result": ...}
      - {"isError": true, "error": {...}}
      - {"error": {...}} (wrapped)
    """
    if raw is None:
        return False, None, {"type": "MCPEmptyResult", "message": "empty result"}

    if isinstance(raw, dict):
        if raw.get("isError") is True:
            err = raw.get("error") or {"message": "tool returned error"}
            return False, None, {"type": "ToolError", "message": str(err), "details": err}

        if "error" in raw and raw["error"] is not None and "content" not in raw:
            err = raw["error"]
            return False, None, {"type": "ToolError", "message": str(err), "details": err}

        if "content" in raw:
            return True, raw.get("content"), None

        if "result" in raw:
            r = raw.get("result")
            if isinstance(r, dict) and "content" in r:
                return True, r.get("content"), None
            return True, r, None

        return True, raw, None

    return True, raw, None


def _extract_receipts(raw: Any) -> List[Receipt]:
    """
    Extract structured receipts best-effort.

    Shapes:
      - {"receipts": [{"kind": "...", "data": {...}}, ...]}
      - {"result": {"receipts": [...]}}
    """
    receipts: list[Receipt] = []

    def _parse_list(lst: Any) -> None:
        if not isinstance(lst, list):
            return
        for item in lst:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind") or item.get("type") or "custom"
            data = item.get("data") if isinstance(item.get("data"), dict) else {"value": item.get("data", item)}
            if kind not in ("file", "network", "process", "resource", "custom"):
                kind = "custom"
            receipts.append(Receipt(kind=kind, data=data))

    if isinstance(raw, dict):
        if "receipts" in raw:
            _parse_list(raw.get("receipts"))
        elif isinstance(raw.get("result"), dict) and "receipts" in raw["result"]:
            _parse_list(raw["result"].get("receipts"))

    return receipts


def _emit_bundled_events(emit: EventEmitter, raw: Any) -> None:
    """
    Some servers/adapters bundle events/progress in the final response.

    Shapes:
      - {"events": [{"type": "progress"|"log"|"partial", "message": "...", "data": {...}}, ...]}
      - {"progress": [...]} (treated as events)
      - {"result": {"events": [...]}}
    """

    def _emit_list(lst: Any) -> None:
        if not isinstance(lst, list):
            return
        for e in lst:
            if not isinstance(e, dict):
                continue
            et = e.get("type") or e.get("kind") or "log"
            if et not in ("progress", "log", "partial"):
                et = "log"
            emit(
                ToolEvent(
                    seq=0,
                    type=et,
                    message=e.get("message"),
                    data=e.get("data"),
                )
            )

    if not isinstance(raw, dict):
        return

    if "events" in raw:
        _emit_list(raw.get("events"))
        return

    if "progress" in raw:
        _emit_list(raw.get("progress"))
        return

    r = raw.get("result")
    if isinstance(r, dict) and "events" in r:
        _emit_list(r.get("events"))
