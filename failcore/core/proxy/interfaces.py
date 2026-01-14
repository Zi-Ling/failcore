# failcore/core/proxy/interfaces.py
"""
Proxy layer abstract interfaces

Defines protocol-agnostic interfaces for proxy components.
This allows core/ to remain independent of specific IO implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Dict, Optional


@dataclass(frozen=True)
class UpstreamResponse:
    """
    Response from upstream provider
    
    This is a pure data structure with no IO dependencies.
    """
    status: int
    headers: Dict[str, str]
    body: bytes


class UpstreamClient(Protocol):
    """
    Abstract upstream client interface
    
    Concrete implementations (e.g. HttpxUpstreamClient) live in infrastructure/
    """
    
    def resolve_url(self, *, provider: str, endpoint: str) -> str:
        """Resolve upstream URL based on provider and endpoint"""
        ...
    
    async def forward_request(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        body: Optional[bytes],
    ) -> UpstreamResponse:
        """Forward HTTP request to upstream provider"""
        ...


class UrlResolver(Protocol):
    """
    Abstract URL resolver interface
    
    Allows pluggable URL resolution strategies.
    """
    
    def resolve(self, *, provider: str, endpoint: str) -> str:
        """Resolve full URL from provider and endpoint"""
        ...
