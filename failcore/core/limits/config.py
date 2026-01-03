"""
P0-2: Reliability Guardrails
Cross-platform resource limits to prevent hangs, explosions, and disk bombs
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LimitsConfig:
    """
    Resource limits for tool execution (local + remote)
    
    Prevents:
    - Infinite hangs (timeout_ms)
    - Memory explosions (max_output_bytes)
    - Event floods (max_events)
    - Disk bombs (max_file_bytes)
    - Concurrency storms (max_concurrency)
    """
    
    # Timeout limits
    timeout_ms: int = 60_000  # 60 seconds default
    
    # Output limits (return value size)
    max_output_bytes: int = 10 * 1024 * 1024  # 10MB
    
    # Event limits (prevent emit() flood)
    max_events: int = 1000
    
    # File limits (per write + total per run)
    max_file_bytes: int = 50 * 1024 * 1024  # 50MB per write
    max_total_file_bytes: Optional[int] = 500 * 1024 * 1024  # 500MB per run
    
    # Concurrency limits (max parallel tool calls)
    max_concurrency: int = 10
    
    @classmethod
    def strict(cls):
        """Strict limits for production"""
        return cls(
            timeout_ms=30_000,
            max_output_bytes=5 * 1024 * 1024,
            max_events=500,
            max_file_bytes=10 * 1024 * 1024,
            max_total_file_bytes=100 * 1024 * 1024,
            max_concurrency=5,
        )
    
    @classmethod
    def lenient(cls):
        """Lenient limits for development"""
        return cls(
            timeout_ms=300_000,  # 5 minutes
            max_output_bytes=100 * 1024 * 1024,
            max_events=10000,
            max_file_bytes=500 * 1024 * 1024,
            max_total_file_bytes=None,  # No total limit
            max_concurrency=50,
        )


__all__ = ["LimitsConfig"]
