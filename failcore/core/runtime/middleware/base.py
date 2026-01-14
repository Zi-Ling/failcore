#failcore/tools/runtime/middleware/base
from __future__ import annotations


from abc import ABC
from typing import Any, Optional, Protocol

from ..types import CallContext, ToolEvent, ToolResult, ToolSpecRef


class Middleware(ABC):
    """
    Base class for ToolRuntime middleware.

    Middleware lifecycle (per tool call):

        1. on_call_start   (pre-execution)
           - Can observe the call
           - Can emit ToolEvent
           - MAY return ToolResult to short-circuit execution
             (e.g. replay/cache hit)

        2. on_call_success (post-execution, success or early-return)
           - Receives final ToolResult
           - Should NOT modify ToolResult in-place

        3. on_call_error   (post-execution, exception path)
           - Observes raised exception
           - Used for audit/logging/metrics/cleanup

    IMPORTANT RULES:
        - Middleware MUST be side-effect free with respect to runtime control flow,
          except via the explicit short-circuit return in on_call_start.
        - Middleware should NOT mutate CallContext.
        - Middleware should NOT generate ToolEvent.seq by itself.
    """

    async def on_call_start(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        emit,
    ) -> Optional[ToolResult]:
        """
        Called before transport execution.

        Return:
            - None: continue execution
            - ToolResult: short-circuit runtime and skip transport.call()

        Typical use cases:
            - Replay / cache hit
            - Dry-run / mock execution
            - Policy pre-deny (return ToolResult with ok=False)
        """
        return None

    async def on_call_success(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        result: ToolResult,
        emit,
    ) -> None:
        """
        Called after successful execution OR short-circuit return.

        Notes:
            - This method is also invoked for short-circuited calls.
            - Middleware should treat result as read-only.
        """
        return None

    async def on_call_error(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        error: Exception,
        emit,
    ) -> None:
        """
        Called when an exception escapes transport.call() or middleware hooks.

        Notes:
            - Runtime will normalize the exception into ToolResult.
            - Middleware should NOT re-raise the exception.
        """
        return None
