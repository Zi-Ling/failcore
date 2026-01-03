from __future__ import annotations

import asyncio
import os
import sys
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

    # ===== MCP init tuning (avoid hard-coding) =====
    # If None, we will use env MCP_PROTOCOL_VERSION or a conservative default.
    protocol_version: Optional[str] = None

    # If None, defaults to {} for maximum compatibility.
    client_capabilities: Optional[Dict[str, Any]] = None

    # Override client info name/version if you want
    client_name: str = "failcore"
    client_version: Optional[str] = None


class McpTransport(BaseTransport):
    """
    MCP transport implementation backed by a long-lived stdio session.
    
    Optimization 3: MCP as Pure Transport
    ======================================
    
    Responsibilities (Protocol ↔ Internal Structure):
    - Encode internal ToolSpecRef/CallContext to MCP JSON-RPC format
    - Decode MCP responses to ToolResult with FailCoreError structure
    - Map MCP notifications to ToolEvent stream
    - Handle MCP session lifecycle (init, reconnect, shutdown)
    
    NOT Responsible For (Delegated to ToolRuntime Middleware):
    - Policy enforcement (done by PolicyMiddleware)
    - Validation (done by ValidationMiddleware)
    - Retry logic (done by RetryMiddleware if added)
    - Audit/trace (done by AuditMiddleware)
    - Caching/replay (done by ReplayMiddleware)
    
    This separation ensures:
    1. MCP protocol changes don't affect business logic
    2. Same middleware works for MCP, Proxy, Local
    3. Transport is easily testable (mock MCP server)
    4. Clear error boundary (NETWORK/DECODE vs VALIDATE/POLICY/EXECUTE)

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

        self._active_emit: Optional[EventEmitter] = None
        self._emit_lock = asyncio.Lock()

        self._session = McpSession(cfg.session, on_notification=self._on_notification)

        # MCP protocol state
        self._initialized = False
        # Prevent concurrent initialize storms if two callers race
        self._init_lock = asyncio.Lock()

    async def shutdown(self) -> None:
        await self._session.shutdown()

    def _resolve_client_version(self) -> str:
        # Prefer explicit config
        if self._cfg.client_version:
            return self._cfg.client_version

        # Try package metadata (safe; if failcore isn't installed as dist, fall back)
        try:
            from importlib.metadata import version as pkg_version  # py3.8+

            return pkg_version("failcore")
        except Exception:
            pass

        # Fall back to configured server_version, then dev
        return self._cfg.server_version or "dev"

    def _resolve_protocol_version(self) -> str:
        # Config > env > conservative default
        if self._cfg.protocol_version:
            return self._cfg.protocol_version
        env_v = os.getenv("MCP_PROTOCOL_VERSION")
        if env_v:
            return env_v
        # Conservative default that worked in your run
        return "2024-11-05"

    def _resolve_capabilities(self) -> Dict[str, Any]:
        # Default to {} for maximum compatibility with strict validators
        if self._cfg.client_capabilities is None:
            return {}
        return self._cfg.client_capabilities

    async def _ensure_initialized(self) -> None:
        """
        Ensure MCP initialize handshake is completed exactly once.

        Many MCP servers require:
          1) initialize (request)
          2) notifications/initialized (notification)
        before any other operations such as tools/list.
        """
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            await self._session.start()

            init_params = {
                "protocolVersion": self._resolve_protocol_version(),
                "capabilities": self._resolve_capabilities(),
                "clientInfo": {
                    "name": self._cfg.client_name,
                    "version": self._resolve_client_version(),
                },
            }

            try:
                _ = await self._session.call("initialize", params=init_params)

                # Best-effort: notify "initialized" (some servers require it, some ignore it)
                # Notification: MUST NOT include "id" and has no response.
                try:
                    await self._session.notify("notifications/initialized", params=None)

                except Exception:
                    # Do not fail init if server doesn't understand/need it
                    pass

                self._initialized = True

            except Exception as e:
                raise McpSessionError(f"MCP initialize failed: {e}") from e

    async def list_tools(self, *, ctx: Optional[CallContext] = None) -> list[ToolSpecRef]:
        """
        List tools from remote MCP server
        
        Error Contract (Scheme 3/4):
        Remote MCP servers MAY return structured errors in the following format:
        {
            "error": {
                "type": "SECURITY" | "PRECONDITION" | "TOOL" | "INTERNAL",
                "error_code": "PATH_TRAVERSAL" | "TOOL_NOT_FOUND" | ...,
                "message": "Human-readable error message",
                "suggestion": "Actionable fix guidance (optional)",
                "remediation": {"template": "...", "vars": {...}} (optional),
                "retryable": true | false (optional)
            }
        }
        
        FailCore will preserve these fields for LLM self-healing.
        """
        await self._ensure_initialized()

        try:
            # Important: use params=None so encoder can omit params entirely (more compatible)
            res = await self._session.call(self._cfg.list_tools_method, params=None)
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
        await self._ensure_initialized()

        print(f"[MCP_TOOL_CALL] tool={tool.name} args_keys={list((args or {}).keys())} run_id={ctx.run_id}", file=sys.stderr)

        async with self._emit_lock:
            self._active_emit = emit

        try:
            emit(ToolEvent(seq=0, type="progress", message="mcp rpc send", data={"tool": tool.name}))

            params = {"name": tool.name, "arguments": args or {}}

            try:
                raw = await self._session.call(self._cfg.call_tool_method, params=params)
            except Exception as e:
                # Optimization 4: Remote-specific error codes with LLM-friendly suggestions
                return ToolResult(
                    ok=False,
                    content=None,
                    raw=None,
                    error=_classify_transport_error(e, tool.name),
                )

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
                raw=raw,
                error=err,
                receipts=receipts,
            )

        finally:
            async with self._emit_lock:
                self._active_emit = None

    async def _on_notification(self, msg: dict[str, Any]) -> None:
        method = msg.get("method")
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

        async with self._emit_lock:
            emit = self._active_emit

        if emit is None:
            return

        message = None
        data: Any = None

        if isinstance(params, dict):
            message = params.get("message") or params.get("text")
            data = params.get("data") if "data" in params else params

        etype = "log"
        if method == self._cfg.progress_method:
            etype = "progress"
        elif method == self._cfg.log_method:
            etype = "log"
        elif method == self._cfg.partial_method:
            etype = "partial"
        elif method == self._cfg.generic_event_method:
            hinted = params.get("type") if isinstance(params, dict) else None
            if hinted in ("progress", "log", "partial"):
                etype = hinted
            else:
                etype = "log"

        emit(
            ToolEvent(
                seq=0,
                type=etype,
                message=message,
                data=data,
            )
        )


# =========================================================
# Helpers (best-effort normalization)
# =========================================================

def _extract_tools_list(res: Any) -> List[Dict[str, Any]]:
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
    Normalize MCP call result into ToolResult format
    
    Scheme 3: Extract structured error fields (error_code, suggestion, remediation)
    if the remote MCP server returns FailCore-compatible errors.
    """
    if raw is None:
        return False, None, {
            "type": "TOOL",
            "error_code": "MCP_EMPTY_RESULT",
            "message": "MCP server returned empty result"
        }

    if isinstance(raw, dict):
        # Check for error indicators
        if raw.get("isError") is True:
            err = raw.get("error") or {"message": "tool returned error"}
            return False, None, _extract_structured_error(err, "ToolError")

        if "error" in raw and raw["error"] is not None and "content" not in raw:
            err = raw["error"]
            return False, None, _extract_structured_error(err, "ToolError")

        # Success paths
        if "content" in raw:
            return True, raw.get("content"), None

        if "result" in raw:
            r = raw.get("result")
            if isinstance(r, dict) and "content" in r:
                return True, r.get("content"), None
            return True, r, None

        return True, raw, None

    return True, raw, None


def _extract_structured_error(err: Any, default_type: str = "TOOL") -> Dict[str, Any]:
    """
    Extract structured error fields from MCP error response
    
    Optimization 1: Unified error contract - transform MCP errors to FailCoreError format
    Optimization 4: Add remote-specific suggestions if not provided by server
    """
    from failcore.core.errors import codes
    
    if isinstance(err, str):
        # Check for common patterns
        if "not found" in err.lower():
            return {
                "type": "TOOL",
                "error_code": codes.REMOTE_TOOL_NOT_FOUND,
                "message": err,
                "phase": "VALIDATE",
                "suggestion": "Verify tool name spelling. Use tools/list to see available tools.",
            }
        return {
            "type": default_type,
            "error_code": "UNKNOWN",
            "message": err
        }
    
    if not isinstance(err, dict):
        return {
            "type": default_type,
            "error_code": "UNKNOWN",
            "message": str(err)
        }
    
    # Build structured error dict
    error_dict = {
        "type": err.get("type", default_type),
        "error_code": err.get("error_code") or err.get("code", "UNKNOWN"),
        "message": err.get("message", str(err)),
    }
    
    # Add phase if present
    if "phase" in err:
        error_dict["phase"] = err["phase"]
    
    # Scheme 3: Extract LLM-friendly fields (if server provided them)
    if "suggestion" in err:
        error_dict["suggestion"] = err["suggestion"]
    if "remediation" in err:
        error_dict["remediation"] = err["remediation"]
    if "hint" in err:
        error_dict["hint"] = err["hint"]
    
    # Optimization 4: Generate suggestion if not provided
    if "suggestion" not in error_dict:
        error_code = error_dict["error_code"]
        message_lower = error_dict["message"].lower()
        
        # Tool not found
        if error_code == "TOOL_NOT_FOUND" or "not found" in message_lower:
            error_dict["error_code"] = codes.REMOTE_TOOL_NOT_FOUND
            error_dict["suggestion"] = "Verify tool name spelling. Use tools/list to see available tools."
            error_dict["phase"] = "VALIDATE"
        
        # Invalid parameters
        elif "parameter" in message_lower or "argument" in message_lower or "missing" in message_lower:
            error_dict["error_code"] = codes.REMOTE_INVALID_PARAMS
            error_dict["suggestion"] = "Check parameter names and types. Refer to tool schema for required fields."
            error_dict["phase"] = "VALIDATE"
    
    # Preserve details (but be careful about sensitive data)
    if "details" in err:
        error_dict["details"] = err["details"]
    
    # Retryable hint for agent loops
    if "retryable" in err:
        error_dict["retryable"] = err["retryable"]
    
    return error_dict


def _classify_transport_error(exc: Exception, tool_name: str) -> Dict[str, Any]:
    """
    Classify transport exceptions into FailCoreError-compatible structure
    
    Optimization 1: Unified error contract for remote calls
    Optimization 4: Remote-specific error codes with suggestions
    """
    from .session import McpTimeout, McpSessionClosed, McpProcessCrashed
    from failcore.core.errors import codes
    
    # Timeout errors
    if isinstance(exc, McpTimeout) or "timeout" in str(exc).lower():
        return {
            "type": "TRANSPORT",
            "error_code": codes.REMOTE_TIMEOUT,
            "message": f"MCP tool '{tool_name}' timed out",
            "phase": "NETWORK",
            "retryable": True,
            "suggestion": "Increase timeout, reduce payload size, or retry with exponential backoff",
            "remediation": {
                "action": "retry_with_config",
                "template": "Retry with timeout={timeout}s and max_retries={max_retries}",
                "vars": {"timeout": 120, "max_retries": 3}
            },
            "details": {"original_error": str(exc)}
        }
    
    # Connection/process errors
    if isinstance(exc, (McpSessionClosed, McpProcessCrashed)):
        return {
            "type": "TRANSPORT",
            "error_code": codes.REMOTE_UNREACHABLE,
            "message": f"MCP server unreachable for tool '{tool_name}'",
            "phase": "NETWORK",
            "retryable": True,
            "suggestion": "Check MCP server is running and accessible. Verify network connectivity.",
            "remediation": {
                "action": "restart_server",
                "template": "Restart MCP server: {command}",
                "vars": {"command": "check server process status"}
            },
            "details": {"original_error": str(exc)}
        }
    
    # Protocol/decode errors
    if "json" in str(exc).lower() or "decode" in str(exc).lower() or "parse" in str(exc).lower():
        return {
            "type": "TRANSPORT",
            "error_code": codes.REMOTE_PROTOCOL_MISMATCH,
            "message": f"MCP protocol error calling '{tool_name}': {exc}",
            "phase": "DECODE",
            "retryable": False,
            "suggestion": "Verify MCP protocol version compatibility. Check for malformed responses.",
            "details": {"original_error": str(exc)}
        }
    
    # Generic transport error
    return {
        "type": "TRANSPORT",
        "error_code": codes.REMOTE_SERVER_ERROR,
        "message": f"MCP server error: {exc}",
        "phase": "EXECUTE",
        "retryable": False,
        "suggestion": "Check MCP server logs for details. Verify tool exists and parameters are correct.",
        "details": {
            "tool": tool_name,
            "exception_type": exc.__class__.__name__,
            "original_error": str(exc)
        }
    }


def _extract_receipts(raw: Any) -> List[Receipt]:
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
