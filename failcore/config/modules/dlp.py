# failcore/config/modules/dlp.py
"""
DLP Module Configuration

Configuration for Data Loss Prevention module.
"""

from dataclasses import dataclass
from typing import Literal
from .base import ModuleConfig


@dataclass(frozen=True)
class DLPConfig(ModuleConfig):
    """
    DLP module configuration.
    
    enabled: If True, DLP ruleset is registered at startup
    mode: Runtime behavior mode (block/sanitize/warn)
    redact: Whether to redact matched patterns in evidence
    max_scan_chars: Maximum characters to scan per payload
    """
    
    enabled: bool = False
    mode: Literal["block", "sanitize", "warn"] = "warn"
    redact: bool = True
    max_scan_chars: int = 65536  # 64KB
    
    @classmethod
    def default(cls) -> "DLPConfig":
        """Default DLP configuration"""
        return cls(
            enabled=False,
            mode="warn",
            redact=True,
            max_scan_chars=65536,
        )
    
    @classmethod
    def strict(cls) -> "DLPConfig":
        """Strict DLP configuration"""
        return cls(
            enabled=True,
            mode="block",
            redact=True,
            max_scan_chars=65536,
        )
