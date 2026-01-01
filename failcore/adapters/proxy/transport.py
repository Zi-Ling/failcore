from __future__ import annotations

from typing import Any, Dict, Optional

from failcore.core.tools.runtime.transports.base import BaseTransport, EventEmitter
from failcore.core.tools.runtime.types import CallContext, ToolResult, ToolSpecRef, ToolEvent


class ProxyTransport(BaseTransport):
    """
    Future transport: route tool calls to a remote proxy service.
    This is a placeholder so TransportFactory can import it without breaking.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = dict(config)

    async def call(
        self,
        *,
        tool: ToolSpecRef,
        args: Dict[str, Any],
        ctx: CallContext,
        emit: EventEmitter,
    ) -> ToolResult:
        emit(ToolEvent(seq=0, type="log", message="ProxyTransport not implemented", data={"tool": tool.name}))
        return ToolResult(
            ok=False,
            content=None,
            raw=None,
            error={"type": "NotImplemented", "message": "ProxyTransport is not implemented yet"},
        )
