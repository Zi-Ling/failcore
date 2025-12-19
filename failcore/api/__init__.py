# failcore/api/__init__.py
"""
FailCore User-facing API

Three levels:
1. Run API (run) - one-line execution for quick testing and demos
2. Session API (Session) - recommended main entry point for real usage
3. Advanced/Core API - in core package for integrators and framework authors
"""

from .run import run
from .session import Session
from . import presets
from .result import Result

__all__ = [
    "run",
    "Session",
    "Result",
    "presets",
]
