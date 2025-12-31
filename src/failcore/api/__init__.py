# failcore/api/base.py
"""
FailCore User-facing API

Three levels:
1. Run API (run) - one-line execution for quick testing and demos
2. Session API (Session) - recommended main entry point for real usage
3. Advanced/Core API - in core package for integrators and framework authors

Magic:
- watch: Decorator for automatic trace and validation
"""

from .run import run
from .session import Session
from . import presets
from .result import Result
from .watch import watch, set_watch_session, WatchContext

__all__ = [
    "run",
    "Session",
    "Result",
    "presets",
    "watch",
    "set_watch_session",
    "WatchContext",
]
