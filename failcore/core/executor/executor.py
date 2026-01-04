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

# Cost tracking imports
try:
    from ..cost import CostGuardian, CostEstimator, CostUsage, UsageExtractor
    from ...infra.storage.cost_tables import CostStorage
    COST_AVAILABLE = True
except ImportError:
    COST_AVAILABLE = False
    CostGuardian = None
    CostEstimator = None
    CostUsage = None
    UsageExtractor = None
    CostStorage = None


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
    enable_cost_tracking: bool = True   # enable cost tracking and metrics


class Executor:
    """
    v0.1.1 executor with structured trace events:
      - record structured events (v0.1.1 schemas)
      - fail-fast validation
      - policy gate
      - tools dispatch
      - cost tracking and budget enforcement
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
        cost_guardian: Optional[Any] = None,
        cost_estimator: Optional[Any] = None,
    ) -> None:
        self.tools = tools
        self.recorder = recorder or TraceRecorder()
        self.policy = policy or Policy()
        self.validator = validator
        self.config = config or ExecutorConfig()
        self.replayer = replayer
        self._attempt_counter = {}
        
        # Cost tracking
        self.cost_guardian = cost_guardian if COST_AVAILABLE else None
        self.cost_estimator = cost_estimator or (CostEstimator() if COST_AVAILABLE and self.config.enable_cost_tracking else None)
        self.cost_storage = CostStorage() if COST_AVAILABLE and self.config.enable_cost_tracking else None
        
        # Runtime cost accumulator (per-run cumulative tracking)
        self._run_cost_cumulative: Dict[str, Dict[str, float]] = {}  # {run_id: {cost_usd, tokens, api_calls}}
        
        # Usage extractor for extracting actual usage from tool outputs
        self.usage_extractor = UsageExtractor() if COST_AVAILABLE and self.config.enable_cost_tracking else None

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
                    # Extract suggestion/remediation from ValidationResult.details
                    details = result.details or {}
                    suggestion = details.get("suggestion")
                    remediation = details.get("remediation")
                    
                    return self._fail(
                        step, ctx, run_ctx, attempt, started_at, t0,
                        result.code or "PRECONDITION_FAILED",  # Use specific code from validator
                        result.message,
                        ExecutionPhase.VALIDATE,
                        details=details,
                        suggestion=suggestion,
                        remediation=remediation,
                    )

        # 3. Cost check (BEFORE policy and execution)
        estimated_usage = None
        if self.cost_guardian and self.cost_estimator:
            # Estimate cost for this step
            tool_metadata = step.meta or {}
            estimated_usage = self.cost_estimator.estimate(
                tool_name=step.tool,
                params=step.params,
                metadata=tool_metadata,
            )
            # Fill in run/step context
            estimated_usage = CostUsage(
                run_id=ctx.run_id,
                step_id=step.id,
                tool_name=step.tool,
                model=estimated_usage.model,
                provider=estimated_usage.provider,
                input_tokens=estimated_usage.input_tokens,
                output_tokens=estimated_usage.output_tokens,
                total_tokens=estimated_usage.total_tokens,
                cost_usd=estimated_usage.cost_usd,
                estimated=True,
                api_calls=estimated_usage.api_calls,
            )
            
            # Check budget (CRITICAL: this can block execution)
            allowed_by_budget, budget_reason, budget_error_code = self.cost_guardian.check_operation(
                estimated_usage,
                raise_on_exceed=False,
            )
            
            if not allowed_by_budget:
                # Budget or burn rate exceeded - produce BLOCKED STEP_END with cost metrics
                cost_metrics = self._build_cost_metrics(ctx.run_id, step, estimated_usage)
                
                # Use the specific error code from guardian
                error_code = budget_error_code or "BUDGET_EXCEEDED"
                
                # Map to canonical error codes
                from ..errors import codes
                if error_code == "BURN_RATE_EXCEEDED":
                    canonical_code = codes.ECONOMIC_BURN_RATE_EXCEEDED
                elif error_code == "BUDGET_COST_EXCEEDED":
                    canonical_code = codes.ECONOMIC_BUDGET_EXCEEDED
                elif error_code == "BUDGET_TOKENS_EXCEEDED":
                    canonical_code = codes.ECONOMIC_TOKEN_LIMIT
                else:
                    canonical_code = codes.ECONOMIC_BUDGET_EXCEEDED
                
                return self._fail(
                    step, ctx, run_ctx, attempt, started_at, t0,
                    canonical_code,
                    budget_reason or "Budget or burn rate exceeded",
                    ExecutionPhase.POLICY,  # Budget check is policy-level protection
                    details={
                        "budget_reason": budget_reason,
                        "budget_error_code": error_code,
                        "estimated_cost_usd": estimated_usage.cost_usd,
                        "estimated_tokens": estimated_usage.total_tokens,
                    },
                    suggestion="Increase budget or wait before retrying" if error_code == "BURN_RATE_EXCEEDED" else "Increase budget or optimize tool usage",
                    metrics=cost_metrics,
                )
        
        # 4. Policy check (with LLM-friendly suggestion support)
        policy_result = self.policy.allow(step, ctx)
        
        # Handle both legacy tuple and modern PolicyResult
        if isinstance(policy_result, tuple):
            # Legacy: (allowed, reason)
            allowed, reason = policy_result
            error_code = None
            suggestion = None
            remediation = None
            details = {}
        else:
            # Modern: PolicyResult with suggestion/remediation
            from ..policy.policy import PolicyResult
            if isinstance(policy_result, PolicyResult):
                allowed = policy_result.allowed
                reason = policy_result.reason
                error_code = policy_result.error_code
                suggestion = policy_result.suggestion
                remediation = policy_result.remediation
                details = policy_result.details
            else:
                # Fallback
                allowed, reason = True, ""
                error_code = None
                suggestion = None
                remediation = None
                details = {}
        
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
            
            # Inject suggestion/remediation from policy into error
            return self._fail(
                step, ctx, run_ctx, attempt, started_at, t0, 
                error_code or "POLICY_DENIED",  # Use specific error code from policy if provided
                reason or "Denied by policy", 
                ExecutionPhase.POLICY,
                suggestion=suggestion,
                remediation=remediation,
                details=details,
            )

        # 5. Replay Hook (CRITICAL: before tool execution)
        if self.replayer:
            replay_result = self._try_replay(step, ctx, run_ctx, attempt, allowed, reason)
            if replay_result:
                return replay_result

        # 6. Dispatch
        fn = self.tools.get(step.tool)
        if fn is None:
            return self._fail(step, ctx, run_ctx, attempt, started_at, t0, "TOOL_NOT_FOUND", f"Tool not found: {step.tool}", ExecutionPhase.EXECUTE)

        try:
            out = fn(**step.params)
            output = self._normalize_output(out)
            finished_at, duration_ms = self._finish_times(t0)
            
            # Extract real usage from tool output (if available)
            actual_usage = None
            if COST_AVAILABLE and UsageExtractor:
                actual_usage = UsageExtractor.extract(
                    tool_output=out,
                    run_id=ctx.run_id,
                    step_id=step.id,
                    tool_name=step.tool,
                )
            
            # Use actual usage if available, otherwise use estimated
            final_usage = actual_usage if actual_usage else estimated_usage
            
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

            # Build cost metrics (incremental + cumulative)
            # Use final_usage (real or estimated)
            # CRITICAL: final_usage is the single source of truth for cost tracking
            # - If actual_usage was extracted from tool output, use it (estimated=False)
            # - Otherwise, use estimated_usage from pre-check (estimated=True)
            # This ensures Guardian and Storage use the same cost value
            cost_metrics = self._build_cost_metrics(ctx.run_id, step, final_usage)
            
            # CRITICAL: Update CostGuardian's budget counter after successful execution
            # This ensures next step's check_operation will see the accumulated cost
            # NOTE: We use final_usage (actual if available, otherwise estimated)
            # This ensures budget counters reflect what was actually spent
            # IMPORTANT: Guardian and Storage both use final_usage, ensuring consistency
            if self.cost_guardian and final_usage:
                try:
                    # Record actual usage to update budget counters
                    # If actual_usage was extracted, use it; otherwise use estimated
                    self.cost_guardian.add_usage(final_usage)
                    
                    # DESIGN NOTE: Pre-check uses estimated_usage (from CostEstimator),
                    # which may not match actual_usage if tool returns usage.cost_usd.
                    # This is a known limitation: pre-check must happen BEFORE execution,
                    # so it can't see the tool's return value.
                    # To ensure accurate pre-check, use step.meta["cost_usd"] to provide
                    # explicit cost overrides for deterministic testing.
                except Exception:
                    # Don't fail execution if budget recording fails
                    pass
            
            # Record STEP_END (with cost metrics)
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
                        metrics=cost_metrics,
                    )
                )
                
                # Record to SQLite cost storage
                if self.cost_storage and cost_metrics:
                    try:
                        incremental = cost_metrics["cost"]["incremental"]
                        cumulative = cost_metrics["cost"]["cumulative"]
                        self.cost_storage.insert_usage(
                            run_id=ctx.run_id,
                            step_id=step.id,
                            seq=seq,
                            tool=step.tool,
                            delta_cost_usd=incremental["cost_usd"],
                            delta_tokens=incremental["tokens"],
                            cumulative_cost_usd=cumulative["cost_usd"],
                            cumulative_tokens=cumulative["tokens"],
                            cumulative_api_calls=cumulative["api_calls"],
                            status="OK",
                            ts=started_at,
                            delta_input_tokens=0,
                            delta_output_tokens=0,
                            delta_api_calls=incremental["api_calls"],
                            error_code=None,
                            estimated=incremental["estimated"],
                            model=incremental.get("pricing_ref"),
                            provider=None,
                            duration_ms=duration_ms,
                        )
                        self.cost_storage.upsert_run(
                            run_id=ctx.run_id,
                            created_at=ctx.created_at,
                            total_cost_usd=cumulative["cost_usd"],
                            total_tokens=cumulative["tokens"],
                            total_api_calls=cumulative["api_calls"],
                            total_steps=seq,
                            last_step_seq=seq,
                            status="running",
                        )
                    except Exception as e:
                        # Don't fail the step if cost storage fails
                        import sys
                        print(f"Warning: Failed to record cost to SQLite: {e}", file=sys.stderr)

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
        suggestion: Optional[str] = None,
        remediation: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> StepResult:
        finished_at, duration_ms = self._finish_times(t0)
        
        # Merge LLM-friendly fields into detail (Scheme 3: Policy → FailCoreError injection)
        merged_detail = detail or details or {}
        if suggestion:
            merged_detail["suggestion"] = suggestion
        if remediation:
            merged_detail["remediation"] = remediation
        
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
                        "detail": merged_detail,
                    },
                    metrics=metrics,
                )
            )
            
            # Record to SQLite cost storage (even for failed/blocked steps)
            if self.cost_storage and metrics and "cost" in metrics:
                try:
                    incremental = metrics["cost"]["incremental"]
                    cumulative = metrics["cost"]["cumulative"]
                    self.cost_storage.insert_usage(
                        run_id=ctx.run_id,
                        step_id=step.id,
                        seq=seq,
                        tool=step.tool,
                        delta_cost_usd=incremental["cost_usd"],
                        delta_tokens=incremental["tokens"],
                        cumulative_cost_usd=cumulative["cost_usd"],
                        cumulative_tokens=cumulative["tokens"],
                        cumulative_api_calls=cumulative["api_calls"],
                        status=trace_status.value if isinstance(trace_status, TraceStepStatus) else str(trace_status),
                        ts=started_at,
                        delta_input_tokens=0,
                        delta_output_tokens=0,
                        delta_api_calls=incremental["api_calls"],
                        error_code=error_code,
                        estimated=incremental["estimated"],
                        model=incremental.get("pricing_ref"),
                        provider=None,
                        duration_ms=duration_ms,
                    )
                    # Update run summary with blocked status if applicable
                    self.cost_storage.upsert_run(
                        run_id=ctx.run_id,
                        created_at=ctx.created_at,
                        total_cost_usd=cumulative["cost_usd"],
                        total_tokens=cumulative["tokens"],
                        total_api_calls=cumulative["api_calls"],
                        total_steps=seq,
                        last_step_seq=seq,
                        status="blocked" if trace_status == TraceStepStatus.BLOCKED else "error",
                        blocked_step_id=step.id if trace_status == TraceStepStatus.BLOCKED else None,
                        blocked_reason=message if trace_status == TraceStepStatus.BLOCKED else None,
                        blocked_error_code=error_code if trace_status == TraceStepStatus.BLOCKED else None,
                    )
                except Exception as e:
                    # Don't fail the step if cost storage fails
                    import sys
                    print(f"Warning: Failed to record cost to SQLite: {e}", file=sys.stderr)

        return StepResult(
            step_id=step.id,
            tool=step.tool,
            status=result_status,  # Use semantic status
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            output=None,
            error=StepError(error_code=error_code, message=self._truncate(message), detail=merged_detail),
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
    
    # ---- cost tracking ----
    
    def _build_cost_metrics(
        self,
        run_id: str,
        step: Step,
        usage: Optional[Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Build cost metrics for STEP_END event
        
        Returns dict with:
        - incremental: cost for this step only
        - cumulative: total cost for run so far
        
        Args:
            run_id: Run ID for cumulative tracking
            step: Current step
            usage: CostUsage object (or None if cost tracking disabled)
        
        Returns:
            metrics dict or None if cost tracking disabled
        """
        if not usage or not self.config.enable_cost_tracking:
            return None
        
        # Incremental (this step only)
        # v0.1.3 schema compliant: only allowed fields
        incremental = {
            "cost_usd": float(usage.cost_usd),
            "tokens": int(usage.total_tokens),
            "api_calls": int(usage.api_calls),
            "estimated": bool(usage.estimated),
        }
        
        # Optional: pricing_ref (format: provider:model:version)
        if usage.model and usage.provider:
            incremental["pricing_ref"] = f"{usage.provider}:{usage.model}"
        
        # Initialize run cumulative if not exists
        if run_id not in self._run_cost_cumulative:
            self._run_cost_cumulative[run_id] = {
                "cost_usd": 0.0,
                "tokens": 0,
                "api_calls": 0,
            }
        
        # Update cumulative
        self._run_cost_cumulative[run_id]["cost_usd"] += float(usage.cost_usd)
        self._run_cost_cumulative[run_id]["tokens"] += int(usage.total_tokens)
        self._run_cost_cumulative[run_id]["api_calls"] += int(usage.api_calls)
        
        # Cumulative (entire run so far)
        cumulative = {
            "cost_usd": float(self._run_cost_cumulative[run_id]["cost_usd"]),
            "tokens": int(self._run_cost_cumulative[run_id]["tokens"]),
            "api_calls": int(self._run_cost_cumulative[run_id]["api_calls"]),
        }
        
        return {
            "cost": {
                "incremental": incremental,
                "cumulative": cumulative,
            }
        }
    
    def reset_run_cost(self, run_id: str) -> None:
        """
        Reset cumulative cost for a run
        
        Useful when starting a new run or resetting counters
        """
        if run_id in self._run_cost_cumulative:
            del self._run_cost_cumulative[run_id]
    
    def get_run_cost(self, run_id: str) -> Dict[str, Any]:
        """
        Get current cumulative cost for a run
        
        Returns:
            Dict with cost_usd, tokens, api_calls
        """
        return self._run_cost_cumulative.get(run_id, {
            "cost_usd": 0.0,
            "tokens": 0,
            "api_calls": 0,
        })