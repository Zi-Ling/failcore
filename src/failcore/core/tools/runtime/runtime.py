from __future__ import annotations

import asyncio
import traceback
from typing import Any, Callable, Iterable, List, Optional

from .types import CallContext, ToolEvent, ToolResult, ToolSpecRef
from .transports.base import BaseTransport
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
                seq=0,
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
                        seq=0,
                        type="error",
                        message=str(exc),
                        data={"exception": exc.__class__.__name__, "traceback": tb},
                    )
                )
                return ToolResult(
                    ok=False,
                    content=None,
                    raw=None,
                    error={"type": exc.__class__.__name__, "message": str(exc)},
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
                    seq=0,
                    type="error",
                    message=str(exc),
                    data={"exception": exc.__class__.__name__, "traceback": tb},
                )
            )

            return ToolResult(
                ok=False,
                content=None,
                raw=None,
                error={"type": exc.__class__.__name__, "message": str(exc)},
            )

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
