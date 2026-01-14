# failcore/core/transports/__init__.py
"""
Transport layer interface

BaseTransport defines the contract between ToolRuntime and concrete backends.
This is a pure interface with no implementation dependencies.
"""

from .base import BaseTransport, EventEmitter

__all__ = [
    "BaseTransport",
    "EventEmitter",
]
