"""
Taint Tracking

Lightweight data tainting at tool boundaries for tracking data flow origins
"""

from .tag import TaintSource, DataSensitivity, TaintTag, TaintedData
from .context import TaintContext
from .sanitizer import DataSanitizer
from .store import TaintStore
from .middleware import TaintMiddleware, DLPMiddleware  # DLPMiddleware for backward compatibility

__all__ = [
    "TaintSource",
    "DataSensitivity",
    "TaintTag",
    "TaintedData",
    "TaintContext",
    "DataSanitizer",
    "TaintStore",
    "TaintMiddleware",
    "DLPMiddleware",  # Backward compatibility alias
]
