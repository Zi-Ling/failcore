# failcore/core/proxy/proxy.py
"""
Proxy configuration
"""

from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class ProxyConfig:
    """
    Proxy server configuration
    
    Design principles:
    - Fail-open by default
    - Bounded queues everywhere
    - Drop evidence before dropping traffic
    """
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Upstream
    upstream_timeout_s: float = 60.0
    upstream_max_retries: int = 2
    
    # Streaming
    enable_streaming: bool = True
    streaming_chunk_size: int = 8192
    streaming_strict_mode: bool = False  # WARN only by default
    
    # DLP
    enable_dlp: bool = True
    dlp_strict_mode: bool = False  # Evidence-only by default
    
    # Queue bounds (fail-safe)
    trace_queue_size: int = 10000
    drop_on_full: bool = True  # Drop evidence, not traffic
    
    # Allowed providers (empty = allow all)
    allowed_providers: Set[str] = field(default_factory=set)
    
    # Run context
    run_id: Optional[str] = None
    
    # Budget (optional cost limit)
    budget: Optional[float] = None


__all__ = ["ProxyConfig"]
