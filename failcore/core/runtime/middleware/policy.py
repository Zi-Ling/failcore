from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from .base import Middleware
from ..types import CallContext, ToolResult, ToolSpecRef, Receipt


class PolicyDecider(Protocol):
    """
    Adapter contract:
      - return (allowed: bool, reason: str|None, details: dict|None)
    """
    async def decide(
        self,
        *,
        tool: ToolSpecRef,
        args: Dict[str, Any],
        ctx: CallContext,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]: ...


@dataclass
class PolicyMiddleware(Middleware):
    """
    Execution-time policy gate.

    Behavior:
      - Pre-call deny -> short-circuit ToolResult(ok=False)
      - Allowed -> continue

    Notes:
      - This is intentionally "dumb adapter".
      - Your real policy engine lives in core/policy/.
    """
    decider: PolicyDecider

    async def on_call_start(self, tool: ToolSpecRef, args: dict[str, Any], ctx: CallContext, emit) -> Optional[ToolResult]:
        allowed, reason, details = await self.decider.decide(tool=tool, args=args, ctx=ctx)
        if allowed:
            return None

        # Deny -> short-circuit (runtime will still run on_call_success for middlewares)
        return ToolResult(
            ok=False,
            content=None,
            raw=None,
            error={
                "type": "PolicyDenied",
                "message": reason or "blocked by policy",
                "details": details or {},
            },
            receipts=[
                Receipt(kind="custom", data={"policy": "denied", "reason": reason, "details": details or {}})
            ],
        )
