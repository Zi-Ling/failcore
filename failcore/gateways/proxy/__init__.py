# failcore/gateways/proxy/__init__.py
"""
Proxy Gateway - HTTP proxy server for LLM provider interception

Deployable ASGI application that intercepts and governs LLM API calls.
"""

from .server import ProxyServer
from .app import create_proxy_app

__all__ = [
    "ProxyServer",
    "create_proxy_app",
]
