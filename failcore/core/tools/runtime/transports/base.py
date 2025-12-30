#failcore/tools/runtime/transports/base
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Protocol

from ..types import CallContext, ToolEvent, ToolResult, ToolSpecRef


# =========================================================
# Event emitter type
# =========================================================

EventEmitter = Callable[[ToolEvent], None]


# =========================================================
# Base Transport Interface
# =========================================================

class BaseTransport(ABC):
    """
    BaseTransport defines the execution contract between ToolRuntime
    and concrete tool backends (MCP, Proxy, Local, etc).

    Design principles:
    - Transport is responsible ONLY for actual execution.
    - Transport MUST NOT implement policy, audit, replay, or caching.
    - Transport MUST emit progress/log/partial events via `emit`.
    - Transport MUST NOT generate ToolEvent.seq (runtime owns ordering).
    """

    @abstractmethod
    async def call(
        self,
        *,
        tool: ToolSpecRef,
        args: Dict[str, Any],
        ctx: CallContext,
        emit: EventEmitter,
    ) -> ToolResult:
        """
        Execute a tool call.

        Args:
            tool:
                Reference to the tool specification.

            args:
                Tool arguments (already validated upstream if needed).

            ctx:
                CallContext created by ToolRuntime.
                Transport should treat this as read-only.

            emit:
                Event emitter callback.
                Transport should emit ToolEvent with:
                    - type: progress | log | partial
                    - message / data as appropriate
                DO NOT set seq / trace_id / run_id.

        Returns:
            ToolResult:
                - ok/content/raw/error populated as appropriate
                - receipts SHOULD be included if side effects occurred
        """
        raise NotImplementedError

    async def list_tools(
        self,
        *,
        ctx: Optional[CallContext] = None,
    ) -> list[ToolSpecRef]:
        """
        Optional: list available tools from this transport.

        Notes:
        - Not all transports support dynamic discovery.
        - Default implementation returns empty list.
        - ctx is optional and may be ignored by the transport.
        """
        return []


# =========================================================
# Optional Transport Capabilities
# =========================================================

class SupportsHealthCheck(Protocol):
    """
    Optional protocol for transports that expose health checks.
    """

    async def health(self) -> Dict[str, Any]: ...


class SupportsShutdown(Protocol):
    """
    Optional protocol for transports that require explicit shutdown
    (e.g. terminating MCP sessions / processes).
    """

    async def shutdown(self) -> None: ...
