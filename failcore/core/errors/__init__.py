# failcore/errors/__init__.py

from .exceptions import FailCoreError
from . import codes


"""
Core error types for Failcore.

This package defines the components responsible for:
- Representing errors
- Categorizing errors
- Handling errors

No side effects on import.
"""



__all__ = [
    "FailCoreError",
    "codes",
]
