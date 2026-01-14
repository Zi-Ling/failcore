#failcore/core/tools/runtime/middleware/replay.py

#failcore/core/tools/runtime/middleware/replay.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from .base import Middleware
from ..types import CallContext, ToolResult, ToolSpecRef, Receipt


class ReplayStore(Protocol):
    """
    Adapter contract for replay/cache.

    key can be (replay_id + tool + args hash) or anything deterministic.
    """
    async def get(
        self,
        *,
        tool: ToolSpecRef,
        args: Dict[str, Any],
        ctx: CallContext,
    ) -> Optional[ToolResult]: ...

    async def put(
        self,
        *,
        tool: ToolSpecRef,
        args: Dict[str, Any],
        ctx: CallContext,
        result: ToolResult,
    ) -> None: ...


@dataclass
class ReplayMiddleware(Middleware):
    """
    Replay / cache short-circuit middleware.

    - on_call_start: if store hit -> return ToolResult (skip transport)
    - on_call_success: if normal execution -> put into store (optional)
    """
    store: ReplayStore
    write_back: bool = True

    async def on_call_start(self, tool: ToolSpecRef, args: dict[str, Any], ctx: CallContext, emit) -> Optional[ToolResult]:
        hit = await self.store.get(tool=tool, args=args, ctx=ctx)
        if hit is None:
            return None

        # mark it so audit can see it in receipts even if you don't change runtime
        hit.receipts = list(hit.receipts) + [Receipt(kind="custom", data={"replay": "hit"})]
        return hit

    async def on_call_success(self, tool: ToolSpecRef, args: dict[str, Any], ctx: CallContext, result: ToolResult, emit) -> None:
        if not self.write_back:
            return
        # If it was a hit, avoid re-put unless you want to refresh
        # (we detect via receipts marker)
        if any(r.kind == "custom" and r.data.get("replay") == "hit" for r in result.receipts):
            return
        await self.store.put(tool=tool, args=args, ctx=ctx, result=result)
