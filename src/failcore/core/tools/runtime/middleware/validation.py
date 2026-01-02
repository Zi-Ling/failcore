# failcore/core/tools/runtime/middleware/validation.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .base import Middleware
from ..types import CallContext, ToolEvent, ToolResult, ToolSpecRef
from ....validate.validator import ValidatorRegistry


@dataclass
class ValidationMiddleware(Middleware):
    """Execution-time validation gate using ValidatorRegistry."""
    validator_registry: ValidatorRegistry

    async def on_call_start(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        emit,
    ) -> Optional[ToolResult]:
        validation_ctx = {
            "tool": tool.name,
            "params": args,  # CRITICAL: validator expects "params" not "args"
            "run_id": ctx.run_id,
            "trace_id": ctx.trace_id,
        }

        results = self.validator_registry.validate_preconditions(tool.name, validation_ctx)

        for r in results:
            if not r.valid:
                if emit:
                    emit(ToolEvent(
                        type="error",
                        message=r.message or "Precondition validation failed",
                        data={
                            "stage": "pre",
                            "validation_type": "precondition",
                            "tool": tool.name,
                            "run_id": ctx.run_id,
                            "trace_id": ctx.trace_id,
                            "code": r.code or "VALIDATION_FAILED",
                            "details": r.details or {},
                        },
                    ))
                
                # Determine error type based on code
                # Security/boundary violations are POLICY, format/schema issues are VALIDATION
                error_code = r.code or "VALIDATION_FAILED"
                is_security_violation = error_code in (
                    "SANDBOX_VIOLATION",
                    "PATH_TRAVERSAL",
                    "SSRF_BLOCKED",
                    "RATE_LIMIT_EXCEEDED",
                )
                error_type = "POLICY" if is_security_violation else "VALIDATION"

                return ToolResult(
                    ok=False,
                    content=None,
                    raw=None,
                    error={
                        "type": error_type,
                        "error_code": error_code,
                        "message": r.message or "Precondition validation failed",
                        "details": r.details or {},
                        "retryable": False,  # Input validation/policy failures are not retryable
                    },
                )

        return None

    async def on_call_success(
        self,
        tool: ToolSpecRef,
        args: dict[str, Any],
        ctx: CallContext,
        result: ToolResult,
        emit,
    ) -> None:
        validation_ctx = {
            "tool": tool.name,
            "params": args,  # CRITICAL: validator expects "params" not "args"
            "result": result.content,
            "run_id": ctx.run_id,
            "trace_id": ctx.trace_id,
        }

        results = self.validator_registry.validate_postconditions(tool.name, validation_ctx)

        for r in results:
            if not r.valid and emit:
                emit(ToolEvent(
                    type="log",
                    message=r.message or "Postcondition validation failed",
                    data={
                        "stage": "post",
                        "validation_type": "postcondition",
                        "tool": tool.name,
                        "run_id": ctx.run_id,
                        "trace_id": ctx.trace_id,
                        "code": r.code or "POSTCONDITION_FAILED",
                        "details": r.details or {},
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
