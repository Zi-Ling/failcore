# failcore/core/bootstrap/base.py
"""
Bootstrap entry points for Failcore.

This package exposes canonical wiring functions for assembling
Failcore components (Executor, Policy, TraceRecorder).

No side effects on import.
"""

from .standard import create_standard_executor

__all__ = [
    "create_standard_executor",
]
