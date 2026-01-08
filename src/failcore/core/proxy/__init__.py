# failcore/core/proxy/__init__.py
"""
Proxy - Core execution chokepoint implementation

HTTP/API proxy that intercepts all LLM provider requests for:
- Trace/audit
- Cost tracking
- DLP scanning
- Policy enforcement
"""

from failcore.core.config.proxy import ProxyConfig
from .server import ProxyServer
from .pipeline import ProxyPipeline
from .stream import StreamHandler

__all__ = ["ProxyConfig", "ProxyServer", "ProxyPipeline", "StreamHandler"]
