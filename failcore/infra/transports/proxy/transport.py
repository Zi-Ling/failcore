from __future__ import annotations

from typing import Any, Dict, Optional
import httpx

from failcore.core.transports.base import BaseTransport, EventEmitter
from failcore.core.runtime.types import CallContext, ToolResult, ToolSpecRef, ToolEvent


class ProxyTransport(BaseTransport):
    """
    Upstream HTTP client for proxy forwarding
    
    Responsibilities:
    - HTTP client (connection pool, timeout, retry)
    - Transparent request forwarding
    - No business logic (pure transport)
    
    Note:
    - Business logic lives in core/proxy/pipeline.py
    - This is pure HTTP client wrapper
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = dict(config)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            timeout = self._config.get("timeout_s", 60.0)
            max_retries = self._config.get("max_retries", 2)
            
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                limits=httpx.Limits(max_connections=100),
                follow_redirects=True,
            )
        return self._client

    async def call(
        self,
        *,
        tool: ToolSpecRef,
        args: Dict[str, Any],
        ctx: CallContext,
        emit: EventEmitter,
    ) -> ToolResult:
        """Route through proxy (future implementation)"""
        emit(ToolEvent(seq=0, type="log", message="ProxyTransport - using direct mode", data={"tool": tool.name}))
        return ToolResult(
            ok=False,
            content=None,
            raw=None,
            error={"type": "NotImplemented", "message": "ProxyTransport routing not implemented yet"},
        )
    
    async def forward_request(
        self,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Forward HTTP request to upstream
        
        Pure transport layer - no business logic.
        
        Args:
            url: Target URL
            method: HTTP method
            headers: Request headers
            body: Request body
        
        Returns:
            Response dict with status, headers, body
        """
        client = await self._get_client()
        
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            content=body,
        )
        
        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response.content,
        }
    
    async def close(self) -> None:
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None