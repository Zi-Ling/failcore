# failcore/core/proxy/pipeline.py
"""
Proxy request pipeline - unified request processing

Pipeline stages:
1. Pre-decision (policy/budget check)
2. Forward to upstream
3. Post-emission (usage/DLP enrichment)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
import time
import json
import hashlib
import logging

from failcore.core.egress import (
    EgressEngine,
    EgressEvent,
    EgressType,
    PolicyDecision,
    RiskLevel,
)

logger = logging.getLogger(__name__)

UrlResolver = Callable[[str, str], str]


def _default_url_resolver(provider: str, endpoint: str) -> str:
    """
    Minimal default resolver.
    - If endpoint is already an absolute URL, return as is.
    - Else fallback to api.{provider}.com + endpoint (NOT reliable for all providers).
    Prefer providing url_resolver or upstream_client.resolve_url().
    """
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    return f"https://api.{provider}.com{endpoint}"


def _normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    # Make header lookup case-insensitive-ish by normalizing keys to lower
    return {str(k).lower(): str(v) for k, v in (headers or {}).items()}


def _summarize_response_headers(headers: Dict[str, str]) -> Dict[str, Optional[str]]:
    h = _normalize_headers(headers)
    return {
        "content-type": h.get("content-type"),
        "request-id": h.get("x-request-id") or h.get("request-id"),
        "openai-request-id": h.get("openai-request-id"),
        "anthropic-request-id": h.get("anthropic-request-id"),
    }


def _is_stream_response(headers: Dict[str, str]) -> bool:
    h = _normalize_headers(headers)
    ct = (h.get("content-type") or "").lower()
    # SSE / event-stream is common for streaming responses
    return "text/event-stream" in ct


def _decode_body(body: Any) -> Tuple[Optional[str], Optional[int], str]:
    """
    Return (text, byte_len, sha256_hex).
    - text is decoded best-effort if bytes/str; otherwise None
    - byte_len is exact bytes length if possible; else None
    - sha256 is computed on bytes if possible, otherwise on UTF-8 of str, else empty string
    """
    if body is None:
        return None, None, ""

    if isinstance(body, (bytes, bytearray)):
        b = bytes(body)
        sha = hashlib.sha256(b).hexdigest()
        try:
            text = b.decode("utf-8", errors="replace")
        except Exception:
            text = None
        return text, len(b), sha

    if isinstance(body, str):
        b = body.encode("utf-8", errors="ignore")
        sha = hashlib.sha256(b).hexdigest()
        return body, len(b), sha

    # dict/list etc: stable-ish hash via JSON dump (best-effort)
    try:
        dumped = json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=str)
        b = dumped.encode("utf-8", errors="ignore")
        sha = hashlib.sha256(b).hexdigest()
        return dumped, len(b), sha
    except Exception:
        return None, None, ""


def _safe_preview(text: Optional[str], limit: int) -> Optional[str]:
    if not text:
        return None
    if limit <= 0:
        return None
    return text[:limit]


def _try_parse_json_body(text: Optional[str]) -> Optional[Any]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


class ProxyPipeline:
    """
    Proxy request pipeline

    Responsibilities:
    - Pre-call egress emit
    - Upstream forwarding
    - Post-call enrichment event

    Design:
    - Synchronous semantics (async function but single awaited upstream call)
    - Fail-open on egress emission errors
    - URL resolution is pluggable via url_resolver or upstream_client.resolve_url()
    """

    def __init__(
        self,
        egress_engine: Optional[EgressEngine] = None,
        upstream_client: Optional[Any] = None,
        *,
        url_resolver: Optional[UrlResolver] = None,
        body_preview_limit: int = 4096,
    ):
        self.egress_engine = egress_engine
        self.upstream_client = upstream_client
        self.url_resolver = url_resolver
        self.body_preview_limit = int(body_preview_limit)

    async def process_request(
        self,
        provider: str,
        endpoint: str,
        method: str,
        headers: Dict[str, str],
        body: Optional[bytes],
        run_id: str,
        step_id: str,
    ) -> Dict[str, Any]:
        start_time = time.time()

        # Stage 1: Pre-call egress event
        pre_event = self._create_pre_event(
            provider, endpoint, method, headers, body, run_id, step_id
        )
        self._safe_emit(pre_event)

        # Stage 2: Pre-decision (future: policy/budget)
        # v1: allow all (fail-open)

        # Stage 3: Forward to upstream
        try:
            response = await self._forward_to_upstream(
                provider, endpoint, method, headers, body
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._emit_post_event(
                provider=provider,
                endpoint=endpoint,
                run_id=run_id,
                step_id=step_id,
                duration_ms=duration_ms,
                response=None,
                error={"type": type(e).__name__, "message": str(e)},
            )
            raise

        # Stage 4: Post-call enrichment emit
        duration_ms = (time.time() - start_time) * 1000
        self._emit_post_event(
            provider=provider,
            endpoint=endpoint,
            run_id=run_id,
            step_id=step_id,
            duration_ms=duration_ms,
            response=response,
            error=None,
        )

        return response

    def _safe_emit(self, event: EgressEvent) -> None:
        if not self.egress_engine:
            return
        try:
            self.egress_engine.emit(event)
        except Exception:
            # must not block proxy
            pass

    def _create_pre_event(
        self,
        provider: str,
        endpoint: str,
        method: str,
        headers: Dict[str, str],
        body: Optional[bytes],
        run_id: str,
        step_id: str,
    ) -> EgressEvent:
        # Decode request body for DLP scanning (but keep it minimal)
        request_body_text = None
        if body:
            try:
                request_body_text = body.decode("utf-8", errors="replace")
            except Exception:
                pass
        
        return EgressEvent(
            egress=EgressType.NETWORK,
            action=f"proxy.{method.lower()}",
            target=f"{provider}/{endpoint}",
            run_id=run_id,
            step_id=step_id,
            tool_name=f"proxy_{provider}",
            decision=PolicyDecision.ALLOW,  # v1: allow (policy stage to be added later)
            risk=RiskLevel.LOW,
            evidence={
                "provider": provider,
                "endpoint": endpoint,
                "method": method,
                "phase": "pre_call",
                # Include request_body for DLP scanning (minimal, text-only)
                "request_body": request_body_text,
            },
        )

    def _emit_post_event(
        self,
        *,
        provider: str,
        endpoint: str,
        run_id: str,
        step_id: str,
        duration_ms: float,
        response: Optional[Dict[str, Any]],
        error: Optional[Dict[str, Any]],
    ) -> None:
        if not self.egress_engine:
            return

        outcome = "ok" if not error else "upstream_error"

        status = None
        resp_headers: Dict[str, str] = {}
        resp_body = None

        if response:
            status = response.get("status")
            resp_headers = response.get("headers") or {}
            resp_body = response.get("body")

        # decode + hash + preview (bounded)
        body_text, body_len, body_sha256 = _decode_body(resp_body)
        body_preview = _safe_preview(body_text, self.body_preview_limit)

        # tool_output: only for JSON non-stream responses (for UsageEnricher)
        tool_output = None
        if response and not _is_stream_response(resp_headers):
            # Only attempt parse if content-type indicates json OR body looks like json
            ct = (_normalize_headers(resp_headers).get("content-type") or "").lower()
            if "application/json" in ct or (body_text and body_text.lstrip().startswith(("{", "["))):
                tool_output = _try_parse_json_body(body_text)

        # IMPORTANT: do not label upstream errors as policy DENY
        decision = PolicyDecision.ALLOW
        risk = RiskLevel.LOW if not error else RiskLevel.MEDIUM

        event = EgressEvent(
            egress=EgressType.NETWORK,
            action="proxy.response",
            target=f"{provider}/{endpoint}",
            run_id=run_id,
            step_id=step_id,
            tool_name=f"proxy_{provider}",
            decision=decision,
            risk=risk,
            evidence={
                "provider": provider,
                "endpoint": endpoint,
                "duration_ms": duration_ms,
                "phase": "post_call",
                "outcome": outcome,
                "status": status,
                "response_headers": _summarize_response_headers(resp_headers),
                "body_len": body_len,
                "body_sha256": body_sha256,
                "body_preview": body_preview,
                "error": error,
                "tool_output": tool_output,
            },
        )

        try:
            self.egress_engine.emit(event)
        except Exception as e:
            # fail-open: do not block proxy
            logger.warning(f"Failed to emit post_call event: {e}")

    async def _forward_to_upstream(
        self,
        provider: str,
        endpoint: str,
        method: str,
        headers: Dict[str, str],
        body: Optional[bytes],
    ) -> Dict[str, Any]:
        if not self.upstream_client:
            raise RuntimeError("upstream_client not configured")

        # Resolve URL
        url: str
        if hasattr(self.upstream_client, "resolve_url") and callable(getattr(self.upstream_client, "resolve_url")):
            # Best: upstream client owns provider mapping
            url = self.upstream_client.resolve_url(provider=provider, endpoint=endpoint)
        elif self.url_resolver:
            url = self.url_resolver(provider, endpoint)
        else:
            url = _default_url_resolver(provider, endpoint)

        # Forward request
        if hasattr(self.upstream_client, "forward_request") and callable(getattr(self.upstream_client, "forward_request")):
            return await self.upstream_client.forward_request(
                url=url,
                method=method,
                headers=headers,
                body=body,
            )

        # Fallback: mock response for testing
        return {
            "status": 200,
            "headers": {"content-type": "application/json"},
            "body": b'{"mock": true}',
        }


__all__ = ["ProxyPipeline", "UrlResolver"]
