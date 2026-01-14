# failcore/infrastructure/proxy/__init__.py
"""
Proxy infrastructure - HTTP client and stream handling

Contains IO-dependent implementations for proxy functionality.
"""

from .upstream import HttpxUpstreamClient, UpstreamResponse

__all__ = [
    "HttpxUpstreamClient",
    "UpstreamResponse",
]
