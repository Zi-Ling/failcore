# failcore/core/proxy/__init__.py
"""
Proxy - Core business logic layer

Contains protocol-agnostic proxy logic for:
- Request pipeline processing
- Stream handling logic
- Abstract interfaces

Gateway implementation moved to gateways/proxy/
IO implementations moved to infrastructure/proxy/
"""

from failcore.config.proxy import ProxyConfig
from .pipeline import ProxyPipeline
from .stream import StreamHandler
from .interfaces import UpstreamClient, UpstreamResponse, UrlResolver

__all__ = [
    "ProxyConfig",
    "ProxyPipeline",
    "StreamHandler",
    "UpstreamClient",
    "UpstreamResponse",
    "UrlResolver",
]
