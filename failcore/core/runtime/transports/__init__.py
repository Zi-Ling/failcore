# failcore/core/runtime/transports/__init__.py
"""
Transport factory - Creates transport instances from configuration

Uses lazy imports to avoid circular dependencies.
"""

from .factory import TransportFactory, TransportFactoryError

__all__ = [
    "TransportFactory",
    "TransportFactoryError",
]
