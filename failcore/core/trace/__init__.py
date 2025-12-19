# failcore/core/trace/__init__.py
"""
Core trace types for Failcore.

This package defines the components responsible for:
- Recording events
- Serializing events
- Storing events

No side effects on import.
"""

from .recorder import JsonlTraceRecorder

__all__ = [
    "JsonlTraceRecorder",
]
