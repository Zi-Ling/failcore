# failcore/core/executor/executor.py
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

from ..trace import (
    build_step_start_event,
    build_step_end_event,
    build_policy_denied_event,
    build_output_normalized_event,
    build_replay_hit_event,
    build_replay_miss_event,
    build_replay_policy_diff_event,
    build_replay_injected_event,
    build_run_context,
    StepStatus as TraceStepStatus,
    ExecutionPhase,
)
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
    v0.1.1 executor with structured trace events:
      - record structured events (v0.1.1 schemas)
      - fail-fast validation
      - policy gate
      - tools dispatch
      - returns StepResult (never raises unless misconfigured)
    """

    def __init__(
        self,
        tools: ToolProvider,
        recorder: Optional[TraceRecorder] = None,
        policy: Optional[Policy] = None,
        validator: Optional[ValidatorRegistry] = None,
        config: Optional[ExecutorConfig] = None,
        replayer: Optional[Any] = None,
    ) -> None:
        self.tools = tools
        self.recorder = recorder or TraceRecorder()
        self.policy = policy or Policy()
        self.validator = validator
        self.config = config or ExecutorConfig()
        self.replayer = replayer
        self._attempt_counter = {}

    # ---- public API ----

    def execute(self, step: Step, ctx: RunContext) -> StepResult:
        started_at = utc_now_iso()
        t0 = time.perf_counter()
        
        # Track attempt number
        attempt = self._attempt_counter.get(step.id, 0) + 1
        self._attempt_counter[step.id] = attempt
        
        # Build run context for tracing
        run_ctx = build_run_context(
            run_id=ctx.run_id,
            created_at=ctx.created_at,
            workspace=None,
            sandbox_root=ctx.sandbox_root,
            cwd=ctx.cwd,
            tags=ctx.tags,
            flags=ctx.flags,
        )

        # Record STEP_START with v0.1.1 format
        if hasattr(self.recorder, 'next_seq'):
            seq = self.recorder.next_seq()
            self._record(
                build_step_start_event(
                    seq=seq,
                    run_context=run_ctx,
                    step_id=step.id,
                    tool=step.tool,
                    params=step.params,
                    attempt=attempt,
                    depends_on=step.depends_on,
                )
            )

        # 1. Basic parameter validation
        ok, err = self._validate_step(step)
        if not ok:
            return self._fail(step, ctx, run_ctx, attempt, started_at, t0, "PARAM_INVALID", err, ExecutionPhase.VALIDATE)

        # 2. Precondition validation
        if self.validator and self.validator.has_preconditions(step.tool):
            validation_context = {
                "step": step,
                "params": step.params,
                "ctx": ctx,
            }
            validation_results = self.validator.validate_preconditions(step.tool, validation_context)
            
            for result in validation_results:
                if not result.valid:
                    return self._fail(
                        step, ctx, run_ctx, attempt, started_at, t0,
                        result.code or "PRECONDITION_FAILED",  # Use specific code from validator
                        result.message,
                        ExecutionPhase.VALIDATE,
                    )

        # 3. Policy check
        allowed, reason = self.policy.allow(step, ctx)
        if not allowed:
            # Record POLICY_DENIED event
            if hasattr(self.recorder, 'next_seq'):
                seq = self.recorder.next_seq()
                self._record(
                    build_policy_denied_event(
                        seq=seq,
                        run_context=run_ctx,
                        step_id=step.id,
                        tool=step.tool,
                        attempt=attempt,
                        policy_id="System-Protection",
                        rule_id="P001",
                        rule_name="PolicyCheck",
                        reason=reason or "Denied by policy",
                    )
                )
            
            return self._fail(step, ctx, run_ctx, attempt, started_at, t0, "POLICY_DENY", reason or "Denied by policy", ExecutionPhase.POLICY)

        # 4. Replay Hook (CRITICAL: before tool execution)
        if self.replayer:
            replay_result = self._try_replay(step, ctx, run_ctx, attempt, allowed, reason)
            if replay_result:
                return replay_result

        # 5. Dispatch
        fn = self.tools.get(step.tool)
        if fn is None:
            return self._fail(step, ctx, run_ctx, attempt, started_at, t0, "TOOL_NOT_FOUND", f"Tool not found: {step.tool}", ExecutionPhase.EXECUTE)

        try:
            out = fn(**step.params)
            output = self._normalize_output(out)
            finished_at, duration_ms = self._finish_times(t0)
            
            # Record OUTPUT_NORMALIZED if type differs from expected
            # Only emit if we have a contract that specifies expected_kind
            warnings = []
            expected_kind = getattr(step, 'contract_output_kind', None) if hasattr(step, 'contract_output_kind') else None
            
            # Only record mismatch if we have an expectation
            if expected_kind and expected_kind != output.kind.value:
                if hasattr(self.recorder, 'next_seq'):
                    seq = self.recorder.next_seq()
                    self._record(
                        build_output_normalized_event(
                            seq=seq,
                            run_context=run_ctx,
                            step_id=step.id,
                            tool=step.tool,
                            attempt=attempt,
                            expected_kind=expected_kind,
                            observed_kind=output.kind.value,
                            reason=f"Output kind mismatch: expected {expected_kind}, got {output.kind.value}",
                        )
                    )
                    warnings.append("OUTPUT_KIND_MISMATCH")

            # Record STEP_END
            if hasattr(self.recorder, 'next_seq'):
                seq = self.recorder.next_seq()
                self._record(
                    build_step_end_event(
                        seq=seq,
                        run_context=run_ctx,
                        step_id=step.id,
                        tool=step.tool,
                        attempt=attempt,
                        status=TraceStepStatus.OK,
                        phase=ExecutionPhase.EXECUTE,
                        duration_ms=duration_ms,
                        output={"kind": output.kind.value, "value": output.value},
                        warnings=warnings if warnings else None,
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
            code = "TOOL_RAISED"
            msg = f"{type(e).__name__}: {e}"
            detail = {}
            if self.config.include_stack:
                detail["stack"] = traceback.format_exc()

            return self._fail(step, ctx, run_ctx, attempt, started_at, t0, code, msg, ExecutionPhase.EXECUTE, detail)

    # ---- replay hook ----

    def _try_replay(
        self,
        step: Step,
        ctx: RunContext,
        run_ctx: Dict[str, Any],
        attempt: int,
        policy_allowed: bool,
        policy_reason: str,
    ) -> Optional[StepResult]:
        """
        Try to replay this step from historical trace
        
        Returns:
            StepResult if replay succeeded (HIT)
            None if replay failed (MISS) - continue normal execution
        """
        # Compute current fingerprint (must match builder.py logic)
        import json
        import hashlib
        params_str = json.dumps(step.params, sort_keys=True)
        params_hash = f"sha256:{hashlib.sha256(params_str.encode()).hexdigest()[:16]}"
        fingerprint_id = f"{step.tool}#{params_hash}"
        
        fingerprint = {
            "id": fingerprint_id,
            "inputs": {
                "params_hash": params_hash,
            }
        }
        
        # Ask replayer to attempt replay
        replay_result = self.replayer.replay_step(
            step_id=step.id,
            tool=step.tool,
            params=step.params,
            fingerprint=fingerprint,
            current_policy_decision=(policy_allowed, policy_reason),
        )
        
        # Record replay events
        if hasattr(self.recorder, 'next_seq'):
            seq = self.recorder.next_seq()
            
            if replay_result.hit_type == "HIT":
                # Record HIT
                self._record(
                    build_replay_hit_event(
                        seq=seq,
                        run_context=run_ctx,
                        step_id=step.id,
                        tool=step.tool,
                        attempt=attempt,
                        mode=self.replayer.mode.value,
                        fingerprint_id=fingerprint["id"],
                        matched_step_id=replay_result.match_info.matched_step.get("step_id", "unknown"),
                        source_trace=self.replayer.trace_path,
                    )
                )
                
                # Check for diffs
                if replay_result.diff_details:
                    policy_diff = replay_result.diff_details.get("policy")
                    if policy_diff:
                        seq = self.recorder.next_seq()
                        self._record(
                            build_replay_policy_diff_event(
                                seq=seq,
                                run_context=run_ctx,
                                step_id=step.id,
                                tool=step.tool,
                                attempt=attempt,
                                historical_decision=policy_diff["historical"],
                                current_decision=policy_diff["current"],
                                historical_reason=policy_diff.get("historical_reason"),
                                current_reason=policy_diff.get("current_reason"),
                            )
                        )
                
                # If mock mode, inject output
                if self.replayer.mode.value == "mock" and replay_result.injected:
                    seq = self.recorder.next_seq()
                    output_kind = replay_result.step_result.output.kind.value if replay_result.step_result.output else "none"
                    self._record(
                        build_replay_injected_event(
                            seq=seq,
                            run_context=run_ctx,
                            step_id=step.id,
                            tool=step.tool,
                            attempt=attempt,
                            fingerprint_id=fingerprint["id"],
                            output_kind=output_kind,
                        )
                    )
                    
                    # Return the injected result
                    return replay_result.step_result
            
            elif replay_result.hit_type == "MISS":
                # Record MISS
                self._record(
                    build_replay_miss_event(
                        seq=seq,
                        run_context=run_ctx,
                        step_id=step.id,
                        tool=step.tool,
                        attempt=attempt,
                        mode=self.replayer.mode.value,
                        fingerprint_id=fingerprint.get("id"),
                        reason=replay_result.message or "No matching fingerprint",
                    )
                )
                
                # MISS: stop replay, don't execute tool
                # Return a special SKIPPED result
                return StepResult(
                    step_id=step.id,
                    tool=step.tool,
                    status=StepStatus.FAIL,
                    started_at=utc_now_iso(),
                    finished_at=utc_now_iso(),
                    duration_ms=0,
                    output=None,
                    error=StepError(
                        error_code="REPLAY_MISS",
                        message=f"Replay miss: {replay_result.message}",
                    ),
                    meta={"replay": True, "hit_type": "MISS"},
                )
        
        # If report mode, don't execute
        if self.replayer.mode.value == "report":
            return StepResult(
                step_id=step.id,
                tool=step.tool,
                status=StepStatus.FAIL,
                started_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                duration_ms=0,
                output=None,
                error=StepError(
                    error_code="REPLAY_REPORT_MODE",
                    message="Report mode - execution skipped",
                ),
                meta={"replay": True, "mode": "report"},
            )
        
        return None

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
        run_ctx: Dict[str, Any],
        attempt: int,
        started_at: str,
        t0: float,
        error_code: str,
        message: str,
        phase: ExecutionPhase,
        detail: Optional[Dict[str, Any]] = None,
    ) -> StepResult:
        finished_at, duration_ms = self._finish_times(t0)
        
        # Determine status based on phase (v0.1.2 semantic)
        if phase in (ExecutionPhase.VALIDATE, ExecutionPhase.POLICY):
            trace_status = TraceStepStatus.BLOCKED
            result_status = StepStatus.BLOCKED
        else:
            trace_status = TraceStepStatus.FAIL
            result_status = StepStatus.FAIL

        # Record STEP_END
        if hasattr(self.recorder, 'next_seq'):
            seq = self.recorder.next_seq()
            self._record(
                build_step_end_event(
                    seq=seq,
                    run_context=run_ctx,
                    step_id=step.id,
                    tool=step.tool,
                    attempt=attempt,
                    status=trace_status,  # Use semantic status
                    phase=phase,
                    duration_ms=duration_ms,
                    error={
                        "code": error_code,
                        "message": self._truncate(message),
                        "detail": detail or {},
                    },
                )
            )

        return StepResult(
            step_id=step.id,
            tool=step.tool,
            status=result_status,  # Use semantic status
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            output=None,
            error=StepError(error_code=error_code, message=self._truncate(message), detail=detail),
            meta={"phase": phase.value},
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
