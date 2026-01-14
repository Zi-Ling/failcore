# failcore/core/tools/runtime/middleware/validation.py
"""
Validation Middleware - Trace/observation only (NOT validation logic).

IMPORTANT: This middleware does NOT perform validation.
Validation is done exclusively by StepValidator in the executor pipeline.

This middleware is for:
- Trace recording (observation)
- Event emission (visibility)
- NOT for policy enforcement or blocking

All validation logic should use ValidationEngine via StepValidator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .base import Middleware
from ..types import CallContext, ToolEvent, ToolResult, ToolSpecRef


@dataclass
class ValidationMiddleware(Middleware):
    """
    Validation middleware for trace/observation only.
    
    NOTE: This middleware does NOT perform validation or blocking.
    Validation is handled exclusively by StepValidator in the executor pipeline.
    
    This middleware only emits trace events for visibility/observation.
    """
    
    async def on_call_start(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        emit,
    ) -> Optional[ToolResult]:
        """
        Emit trace event for tool call start (observation only).
        
        NOTE: This does NOT validate or block. Validation is done by StepValidator.
        """
        if emit:
            emit(ToolEvent(
                type="log",
                message=f"Tool call start: {tool.name}",
                data={
                    "stage": "pre",
                    "validation_type": "observation",
                    "tool": tool.name,
                    "run_id": ctx.run_id,
                    "trace_id": ctx.trace_id,
                    "note": "Validation is performed by StepValidator, not this middleware",
                },
            ))
        
        # Never block - return None to continue execution
        return None

    async def on_call_success(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        result: ToolResult,
        emit,
    ) -> None:
        """
        Emit trace event for tool call success (observation only).
        """
        if emit:
            emit(ToolEvent(
                type="log",
                message=f"Tool call success: {tool.name}",
                data={
                    "stage": "post",
                    "validation_type": "observation",
                    "tool": tool.name,
                    "run_id": ctx.run_id,
                    "trace_id": ctx.trace_id,
                },
            ))

    async def on_call_error(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        error: Exception,
        emit,
    ) -> None:
        """Emit tool execution error for trace/audit visibility."""
        if emit:
            emit(ToolEvent(
                type="error",
                message=str(error)[:500],
                data={
                    "stage": "exec",
                    "tool": tool.name,
                    "run_id": ctx.run_id,
                    "trace_id": ctx.trace_id,
                    "error_type": type(error).__name__,
                },
            ))


__all__ = ["ValidationMiddleware"]
