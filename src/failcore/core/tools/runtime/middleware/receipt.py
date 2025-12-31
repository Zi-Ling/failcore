#failcore/core/tools/runtime/middleware/receipt.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .base import Middleware
from ..types import CallContext, ToolResult, ToolSpecRef, Receipt


@dataclass
class ReceiptMiddleware(Middleware):
    """
    Optional middleware to post-process receipts.

    Typical uses:
      - normalize receipt shapes
      - attach common metadata
      - aggregate into a single summary receipt
    """
    normalizer: Optional[Callable[[list[Receipt]], list[Receipt]]] = None

    async def on_call_success(self, tool: ToolSpecRef, args: dict, ctx: CallContext, result: ToolResult, emit) -> None:
        if self.normalizer is None:
            return
        result.receipts = self.normalizer(result.receipts)
