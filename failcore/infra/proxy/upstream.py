# failcore/core/proxy/upstream.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import httpx


@dataclass(frozen=True)
class UpstreamResponse:
    status: int
    headers: Dict[str, str]
    body: bytes


class HttpxUpstreamClient:
    """
    Minimal upstream forwarder for FailCore Proxy.

    - resolve_url(provider, endpoint): choose upstream base URL
    - forward_request(url, method, headers, body): perform real HTTP request
    """

    def __init__(
        self,
        *,
        timeout_s: float = 60.0,
        max_retries: int = 0,
        default_upstream: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        anthropic_base_url: Optional[str] = None,
    ):
        self.timeout_s = float(timeout_s)
        self.max_retries = int(max_retries)
        self.default_upstream = default_upstream.rstrip("/") if default_upstream else None

        self.openai_base_url = (openai_base_url or "https://api.openai.com").rstrip("/")
        self.anthropic_base_url = (anthropic_base_url or "https://api.anthropic.com").rstrip("/")

        # One shared client
        self._client = httpx.AsyncClient(timeout=self.timeout_s)

    def resolve_url(self, *, provider: str, endpoint: str) -> str:
        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"

        if self.default_upstream:
            return f"{self.default_upstream}{endpoint}"

        p = (provider or "").lower()

        # Proxy receives endpoint like /v1/chat/completions for OpenAI
        if p == "openai":
            return f"{self.openai_base_url}{endpoint}"
        if p == "anthropic":
            return f"{self.anthropic_base_url}{endpoint}"

        # Fallback: treat provider as a full base URL if it looks like it
        if p.startswith("http://") or p.startswith("https://"):
            return f"{p.rstrip('/')}{endpoint}"

        # Default: OpenAI base
        return f"{self.openai_base_url}{endpoint}"

    async def forward_request(self, *, url: str, method: str, headers: Dict[str, str], body: Optional[bytes]) -> Dict[str, object]:
        """
        Return dict compatible with ProxyPipeline expectations:
          {"status": int, "headers": {..}, "body": bytes}
        """
        # Remove hop-by-hop / unsafe headers
        clean_headers = {}
        for k, v in (headers or {}).items():
            lk = k.lower()
            if lk in ("host", "content-length", "connection", "proxy-connection", "keep-alive", "transfer-encoding", "upgrade"):
                continue
            # Do not forward FailCore control headers upstream
            if lk.startswith("x-failcore-"):
                continue
            clean_headers[k] = v

        req_body = body or b""

        last_err: Optional[Exception] = None
        attempts = max(1, 1 + self.max_retries)
        for _ in range(attempts):
            try:
                resp = await self._client.request(
                    method=method,
                    url=url,
                    headers=clean_headers,
                    content=req_body,
                )
                # Keep headers minimal + stringified
                out_headers = {k.lower(): v for k, v in resp.headers.items()}
                return {"status": resp.status_code, "headers": out_headers, "body": resp.content}
            except Exception as e:
                last_err = e

        raise RuntimeError(f"upstream request failed: {last_err}") from last_err

    async def aclose(self) -> None:
        await self._client.aclose()
