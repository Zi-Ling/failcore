# failcore/api/__init__.py
"""
FailCore User-facing API

Recommended usage:
- run() + @guard(): Modern context manager style with decorator support
- Session: Legacy API for backward compatibility

New features:
- run: Context manager unifying trace / sandbox / policy
- guard: Decorator that auto-inherits run configuration
"""

from .run import run
from .session import Session
from .guard import guard
from .result import Result

__all__ = [
    "run",
    "Session",
    "guard",
    "Result",
    "presets",
]
