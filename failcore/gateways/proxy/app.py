# failcore/gateways/proxy/app.py
"""
Proxy gateway application factory

Composes core business logic with infrastructure implementations
to create a deployable ASGI application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from failcore.core.proxy import ProxyConfig, ProxyPipeline, StreamHandler
from failcore.core.egress import EgressEngine, TraceSink, UsageEnricher, DLPEnricher, TaintEnricher
# ProxyServer imported lazily in create_proxy_app() to avoid circular dependency


def create_proxy_app(
    *,
    config: ProxyConfig,
    trace_path: Path,
    upstream_client,
) :
    """
    Build the ASGI app for FailCore Proxy.

    This is the single composition root used by:
    - CLI: failcore proxy
    - Tests: httpx.ASGITransport(app=...)
    """
    trace_sink = TraceSink(trace_path, async_mode=False, buffer_size=1, flush_interval_s=0.0)
    enrichers = [UsageEnricher(), DLPEnricher(), TaintEnricher()]
    egress_engine = EgressEngine(trace_sink=trace_sink, enrichers=enrichers)

    pipeline = ProxyPipeline(egress_engine=egress_engine, upstream_client=upstream_client)
    streaming_handler = StreamHandler(strict_mode=config.streaming_strict_mode)

    # Lazy import to avoid circular dependency
    from failcore.gateways.proxy.server import ProxyServer
    server = ProxyServer(config=config, pipeline=pipeline, streaming_handler=streaming_handler)

    return server.app, egress_engine


