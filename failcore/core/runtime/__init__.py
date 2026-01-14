# failcore/core/runtime/__init__.py
"""
Tool runtime - Execution pipeline for tool invocation

Provides ToolRuntime and associated types for executing tools through
a middleware pipeline with policy enforcement, audit, and tracing.
"""

from __future__ import annotations

from .runtime import ToolRuntime
from .types import (
    CallContext,
    ToolEvent,
    ToolResult,
    ToolSpecRef,
    Receipt,
)

__all__ = [
    "ToolRuntime",
    "CallContext",
    "ToolEvent",
    "ToolResult",
    "ToolSpecRef",
    "Receipt",
]
