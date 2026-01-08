# failcore/core/process/__init__.py
"""
Process management utilities for FailCore

Provides process registry and ownership tracking for enforcing
security policies around process lifecycle management.
"""

from .registry import ProcessRegistry

__all__ = ["ProcessRegistry"]
