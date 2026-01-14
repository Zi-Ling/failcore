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
from .guard import guard
from .result import Result

# Validation runtime utilities
def get_default_registry():
    """
    Get application-level validator registry (singleton).
    
    This registry is created once and reused across runs for performance.
    It automatically registers all builtin validators.
    
    Returns:
        ValidatorRegistry instance (application-level singleton)
    
    Example:
        >>> from failcore.api import get_default_registry
        >>> registry = get_default_registry()
        >>> engine = ValidationEngine(registry=registry, policy=policy)
    """
    from .context import _get_app_registry
    return _get_app_registry()

__all__ = [
    "run",
    "guard",
    "Result",
    "presets",
    "get_default_registry",
]
