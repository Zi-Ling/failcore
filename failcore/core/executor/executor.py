# failcore/core/executor/tool_runner.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple
import time
import traceback

from ..step import (
    Step,
    RunContext,
    StepResult,
    StepStatus,
    StepError,
    StepOutput,
    OutputKind,
    ArtifactRef,
    utc_now_iso,
)

from .lifecycle import TraceEvent, TraceEventType
from ..tools import ToolProvider
from ..validate import ValidatorRegistry


# ---------------------------
# Policy (optional interface)
# ---------------------------

class PolicyDeny(Exception):
    """
    Raised when policy denies an action.
    """


class Policy:
    """
    Minimal policy interface. Implement your own in core/policy/policy.py later.
    """
    def allow(self, step: Step, ctx: RunContext) -> Tuple[bool, str]:
        return True, ""


# ---------------------------
# Trace Recorder (optional interface)
# ---------------------------

class TraceRecorder:
    """
    Minimal recorder interface. Your real implementation will live in core/trace/recorder.py.
    """
    def record(self, event: TraceEvent) -> None:
        # no-op by default
        return


# ---------------------------
# Executor
# ---------------------------

@dataclass
class ExecutorConfig:
    strict: bool = True                 # fail-fast always, but reserved for future
    include_stack: bool = True          # include stack in meta on failure
    summarize_limit: int = 200          # truncate long strings in summaries


class Executor:
    """
    v0.1 minimal executor:
      - record STEP_START / STEP_OK / STEP_FAIL
      - fail-fast validation (basic)
      - policy gate (optional)
      - tools dispatch via ToolRegistry
      - returns StepResult (never raises unless misconfigured)
    """

    def __init__(
        self,
        tools: ToolProvider,
        recorder: Optional[TraceRecorder] = None,
        policy: Optional[Policy] = None,
        validator: Optional[ValidatorRegistry] = None,
        config: Optional[ExecutorConfig] = None,
    ) -> None:
        self.tools = tools
        self.recorder = recorder or TraceRecorder()
        self.policy = policy or Policy()
        self.validator = validator  # 可选的验证器注册表
        self.config = config or ExecutorConfig()

    # ---- public API ----

    def execute(self, step: Step, ctx: RunContext) -> StepResult:
        started_at = utc_now_iso()
        t0 = time.perf_counter()

        # Record start
        self._record(
            TraceEvent(
                type=TraceEventType.STEP_START,
                ts=started_at,
                run_id=ctx.run_id,
                step_id=step.id,
                tool=step.tool,
                params_summary=self._summarize_params(step.params),
            )
        )

        # 1. 基础参数验证
        ok, err = self._validate_step(step)
        if not ok:
            return self._fail(step, ctx, started_at, t0, "PARAM_INVALID", err, meta={"phase": "validate"})

        # 2. 前置条件验证（拒绝机制）
        if self.validator and self.validator.has_preconditions(step.tool):
            validation_context = {
                "step": step,
                "params": step.params,
                "ctx": ctx,
            }
            validation_results = self.validator.validate_preconditions(step.tool, validation_context)
            
            # 检查是否有验证失败
            for result in validation_results:
                if not result.valid:
                    return self._fail(
                        step, ctx, started_at, t0,
                        "PRECONDITION_FAILED",
                        result.message,
                        meta={"phase": "precondition", "details": result.details}
                    )

        # 3. 策略检查（拒绝机制）
        allowed, reason = self.policy.allow(step, ctx)
        if not allowed:
            return self._fail(step, ctx, started_at, t0, "POLICY_DENY", reason or "Denied by policy", meta={"phase": "policy"})

        # Dispatch
        fn = self.tools.get(step.tool)
        if fn is None:
            return self._fail(step, ctx, started_at, t0, "TOOL_NOT_FOUND", f"Tool not found: {step.tool}", meta={"phase": "dispatch"})

        try:
            out = fn(**step.params)
            output = self._normalize_output(out)
            finished_at, duration_ms = self._finish_times(t0)

            # Record ok
            self._record(
                TraceEvent(
                    type=TraceEventType.STEP_OK,
                    ts=finished_at,
                    run_id=ctx.run_id,
                    step_id=step.id,
                    tool=step.tool,
                    output_summary=self._summarize_output(output),
                    duration_ms=duration_ms,
                )
            )

            return StepResult(
                step_id=step.id,
                tool=step.tool,
                status=StepStatus.OK,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                output=output,
                error=None,
                meta={},
            )

        except Exception as e:
            # Map exception -> error_code
            code = "TOOL_RAISED"
            msg = f"{type(e).__name__}: {e}"
            meta: Dict[str, Any] = {"phase": "tools"}
            if self.config.include_stack:
                meta["stack"] = traceback.format_exc()

            return self._fail(step, ctx, started_at, t0, code, msg, meta=meta)

    # ---- internals ----

    def _validate_step(self, step: Step) -> Tuple[bool, str]:
        if not step.id.strip():
            return False, "step.id is empty"
        if not step.tool.strip():
            return False, "step.tools is empty"
        if not isinstance(step.params, dict):
            return False, "step.params must be a dict"
        # v0.1: forbid None keys, forbid non-str keys
        for k in step.params.keys():
            if not isinstance(k, str) or not k.strip():
                return False, f"invalid param key: {k!r}"
        return True, ""

    def _fail(
        self,
        step: Step,
        ctx: RunContext,
        started_at: str,
        t0: float,
        error_code: str,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> StepResult:
        finished_at, duration_ms = self._finish_times(t0)

        # Record fail
        self._record(
            TraceEvent(
                type=TraceEventType.STEP_FAIL,
                ts=finished_at,
                run_id=ctx.run_id,
                step_id=step.id,
                tool=step.tool,
                error_code=error_code,
                error_message=self._truncate(message),
                duration_ms=duration_ms,
                meta=meta or {},
            )
        )

        return StepResult(
            step_id=step.id,
            tool=step.tool,
            status=StepStatus.FAIL,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            output=None,
            error=StepError(error_code=error_code, message=self._truncate(message), detail=meta),
            meta={},
        )

    def _record(self, event: TraceEvent) -> None:
        try:
            self.recorder.record(event)
        except Exception:
            # failcore principle: execution should not crash because tracing failed
            return

    def _finish_times(self, t0: float) -> Tuple[str, int]:
        finished_at = utc_now_iso()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        return finished_at, duration_ms

    # ---- output normalization / summarization ----

    def _normalize_output(self, out: Any) -> StepOutput:
        # If a tools already returns StepOutput, trust it
        if isinstance(out, StepOutput):
            return out

        # If tools returns primitive types (int, float, bool), wrap them in JSON
        if isinstance(out, (int, float, bool)):
            return StepOutput(kind=OutputKind.JSON, value=out)

        # If tools returns artifacts list
        if isinstance(out, list) and all(isinstance(x, ArtifactRef) for x in out):
            return StepOutput(kind=OutputKind.ARTIFACTS, value=None, artifacts=out)  # type: ignore[arg-type]

        # Dict -> JSON
        if isinstance(out, dict):
            return StepOutput(kind=OutputKind.JSON, value=out)

        # Bytes -> BYTES
        if isinstance(out, (bytes, bytearray)):
            return StepOutput(kind=OutputKind.BYTES, value=f"<{len(out)} bytes>")

        # Str -> TEXT
        if isinstance(out, str):
            return StepOutput(kind=OutputKind.TEXT, value=out)

        # Fallback
        return StepOutput(kind=OutputKind.UNKNOWN, value=out)

    def _summarize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Keep it safe for trace; avoid huge payloads.
        return {k: self._summarize_value(v) for k, v in params.items()}

    def _summarize_output(self, output: StepOutput) -> Dict[str, Any]:
        return {
            "kind": output.kind.value,
            "value": self._summarize_value(output.value),
            "artifacts": [
                {"uri": a.uri, "kind": a.kind, "name": a.name, "media_type": a.media_type}
                for a in (output.artifacts or [])
            ],
        }

    def _summarize_value(self, v: Any) -> Any:
        if v is None or isinstance(v, (bool, int, float)):
            return v
        if isinstance(v, str):
            return self._truncate(v)
        if isinstance(v, (bytes, bytearray)):
            return f"<{len(v)} bytes>"
        if isinstance(v, dict):
            # shallow summarize
            out: Dict[str, Any] = {}
            for i, (k, vv) in enumerate(v.items()):
                if i >= 20:
                    out["..."] = f"+{len(v)-20} more"
                    break
                out[str(k)] = self._summarize_value(vv)
            return out
        if isinstance(v, list):
            return [self._summarize_value(x) for x in v[:20]] + (["..."] if len(v) > 20 else [])
        return self._truncate(str(v))

    def _truncate(self, s: str) -> str:
        limit = self.config.summarize_limit
        if len(s) <= limit:
            return s
        return s[:limit] + f"...(+{len(s)-limit} chars)"
