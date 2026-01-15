# /failcore/core/runtime/runtime.py
from __future__ import annotations

import asyncio
import sys
import traceback
from typing import Any, Callable, Iterable, List, Optional

from .types import CallContext, ToolEvent, ToolResult, ToolSpecRef
from failcore.core.transports.base import BaseTransport
from .middleware.base import Middleware

EventEmitter = Callable[[ToolEvent], None]


class ToolRuntime:
    """
    ToolRuntime is the execution-time pipeline for tool invocation.

    Key features:
    - Serializes tool calls by default (safe for MCP stdio / single-session backends)
    - Emits ordered ToolEvent stream (seq assigned by runtime)
    - Runs middleware chain (audit / policy / replay / receipt)
    - Supports early short-circuit (Replay) via on_call_start() -> Optional[ToolResult]
    """

    def __init__(
        self,
        transport: BaseTransport,
        middlewares: Optional[Iterable[Middleware]] = None,
        *,
        serialize_calls: bool = True,
    ) -> None:
        self._transport = transport
        self._middlewares: List[Middleware] = list(middlewares or [])
        self._seq: int = 0
        self._serialize_calls = serialize_calls
        self._lock = asyncio.Lock()

    # =========================================================
    # Public API
    # =========================================================

    async def call(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        emit: Optional[EventEmitter] = None,
    ) -> ToolResult:
        """
        Execute a tool call through runtime pipeline.

        Middleware contract (recommended):
          - on_call_start(...) -> Optional[ToolResult]
            Return ToolResult to short-circuit transport (Replay/cache hit).
          - on_call_success(...)
          - on_call_error(...)

        Transport contract:
          - call(tool, args, ctx, emit) -> ToolResult
        """
        if self._serialize_calls:
            async with self._lock:
                return await self._call_inner(tool, args, ctx, emit)
        return await self._call_inner(tool, args, ctx, emit)

    # =========================================================
    # Internal execution
    # =========================================================

    async def _call_inner(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        emit: Optional[EventEmitter],
    ) -> ToolResult:
        # Observability: RUNTIME_INVOKE
        print(f"[RUNTIME_INVOKE] tool={tool.name} run_id={ctx.run_id} trace_id={ctx.trace_id}", file=sys.stderr)

        emitter = emit or (lambda _e: None)

        def _emit(event: ToolEvent) -> None:
            # Runtime owns ordering/correlation
            event.seq = self._next_seq()
            event.trace_id = ctx.trace_id
            event.run_id = ctx.run_id
            emitter(event)

        # ---- START event ----
        _emit(
            ToolEvent(
                type="start",
                message=f"tool call start: {tool.name}",
                data={"tool": tool.name, "args": args},
            )
        )

        # ---- Pre-call middleware (allow short-circuit) ----
        early: Optional[ToolResult] = None
        for mw in self._middlewares:
            maybe = await mw.on_call_start(tool, args, ctx, _emit)
            # Keep the first early result, but still let remaining middlewares observe start.
            if early is None and maybe is not None:
                early = maybe

        # ---- Short-circuit path (Replay/cache hit) ----
        if early is not None:
            try:
                for mw in reversed(self._middlewares):
                    await mw.on_call_success(tool, args, ctx, early, _emit)

                _emit(
                    ToolEvent(
                        seq=0,
                        type="result",
                        message="tool call short-circuited (early result)",
                        data={"ok": early.ok, "short_circuit": True},
                    )
                )
                return early
            except Exception as exc:
                tb = traceback.format_exc()
                for mw in reversed(self._middlewares):
                    await mw.on_call_error(tool, args, ctx, exc, _emit)

                _emit(
                    ToolEvent(
                        type="error",
                        message=str(exc),
                        data={"exception": exc.__class__.__name__, "traceback": tb},
                    )
                )
                
                # Classify error type
                error_type = self._classify_exception_type(exc)
                error_code = self._classify_exception_code(exc)
                
                return ToolResult(
                    ok=False,
                    content=None,
                    raw=None,
                    error={
                        "type": error_type,
                        "error_code": error_code,
                        "message": str(exc),
                        "details": {
                            "exception_class": exc.__class__.__name__,
                            "traceback": tb[:500],
                        },
                        "retryable": error_type == "TRANSPORT",
                    },
                )

        # ---- Execute via transport ----
        try:
            result = await self._transport.call(
                tool=tool,
                args=args,
                ctx=ctx,
                emit=_emit,
            )

            for mw in reversed(self._middlewares):
                await mw.on_call_success(tool, args, ctx, result, _emit)

            _emit(
                ToolEvent(
                    seq=0,
                    type="result",
                    message="tool call completed",
                    data={"ok": result.ok, "short_circuit": False},
                )
            )
            return result

        except Exception as exc:
            tb = traceback.format_exc()

            for mw in reversed(self._middlewares):
                await mw.on_call_error(tool, args, ctx, exc, _emit)

            _emit(
                ToolEvent(
                    type="error",
                    message=str(exc),
                    data={"exception": exc.__class__.__name__, "traceback": tb},
                )
            )
            
            # Classify error type based on exception
            error_type = self._classify_exception_type(exc)
            error_code = self._classify_exception_code(exc)

            return ToolResult(
                ok=False,
                content=None,
                raw=None,
                error={
                    "type": error_type,
                    "error_code": error_code,
                    "message": str(exc),
                    "details": {
                        "exception_class": exc.__class__.__name__,
                        "traceback": tb[:500],  # Truncate for readability
                    },
                    "retryable": error_type == "TRANSPORT",  # Network errors might be retryable
                },
            )

    # =========================================================
    # Error classification
    # =========================================================
    
    def _classify_exception_type(self, exc: Exception) -> str:
        """
        Classify exception into error type taxonomy.
        
        Returns:
            "TRANSPORT" | "TOOL" | "INTERNAL"
        """
        exc_name = exc.__class__.__name__
        
        # Network/protocol errors
        if any(keyword in exc_name.lower() for keyword in [
            "connection", "timeout", "network", "socket", "http", "rpc", "protocol"
        ]):
            return "TRANSPORT"
        
        # I/O errors (file system, permissions)
        if any(keyword in exc_name.lower() for keyword in [
            "filenotfound", "permission", "io", "oserror", "notfound"
        ]):
            return "TOOL"  # I/O errors are tool-layer issues
        
        # Tool execution failures
        if any(keyword in exc_name.lower() for keyword in [
            "runtime", "execution", "tool", "value", "type", "attribute"
        ]):
            return "TOOL"
        
        # Everything else is internal (FailCore bug)
        return "INTERNAL"
    
    def _classify_exception_code(self, exc: Exception) -> str:
        """
        Classify exception into specific error code.
        
        Returns:
            Specific error code (IO_ERROR, RPC_ERROR, etc.)
        """
        exc_name = exc.__class__.__name__
        
        # Network/protocol
        if "timeout" in exc_name.lower():
            return "TIMEOUT"
        if any(keyword in exc_name.lower() for keyword in ["connection", "socket", "network"]):
            return "CONNECTION_ERROR"
        if any(keyword in exc_name.lower() for keyword in ["rpc", "protocol", "http"]):
            return "RPC_ERROR"
        
        # I/O
        if "filenotfound" in exc_name.lower() or "notfound" in exc_name.lower():
            return "FILE_NOT_FOUND"
        if "permission" in exc_name.lower():
            return "PERMISSION_DENIED"
        if "io" in exc_name.lower() or "oserror" in exc_name.lower():
            return "IO_ERROR"
        
        # Tool runtime
        if "value" in exc_name.lower():
            return "INVALID_VALUE"
        if "type" in exc_name.lower():
            return "TYPE_ERROR"
        if "attribute" in exc_name.lower():
            return "ATTRIBUTE_ERROR"
        
        # Generic
        return "TOOL_EXECUTION_ERROR"

    # =========================================================
    # Sequence generator
    # =========================================================

    def _next_seq(self) -> int:
        """
        Generate a monotonic sequence number for ToolEvent.

        NOTE:
        - Runtime owns ordering.
        - Transport and middleware must NOT generate seq.
        """
        self._seq += 1
        return self._seq
