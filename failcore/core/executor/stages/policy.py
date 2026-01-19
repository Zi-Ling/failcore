# failcore/core/executor/stages/policy.py
"""
Policy Stage - policy check and decision recording
"""

from typing import Optional, Any, Dict

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult
from ...trace import ExecutionPhase, build_policy_denied_event
from ...trace.events import TraceEvent, EventType, LogLevel, utc_now_iso
from ...trace.events import TraceEvent, EventType, LogLevel, utc_now_iso


class PolicyStage:
    """Stage 4: Policy check"""
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Check policy and record decision
        
        Unified policy check chain (fixed order, documented):
        1. Side-effect boundary gate (pre-execution fast check)
        2. Semantic guard (high-confidence malicious pattern detection)
        3. Taint tracking/DLP (data loss prevention)
        4. Main policy check (user/system policy)
        
        All guards must return PolicyResult - single interception point.
        Only PolicyStage decides whether to BLOCK (returns StepResult).
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult if policy denies, None otherwise
        
        Note:
            - Sets state.policy_result
            - Sets state.predicted_side_effects
            - Records POLICY_DENIED event if denied (unified event type)
            - All guards use same event type (POLICY_DENIED) with source in details
        """
        # Phase 1: Side-effect boundary gate (fast pre-execution check)
        # Order: side_effect → semantic → policy.allow (fixed, documented)
        if services.side_effect_gate:
            allowed, gate_result, predicted = services.side_effect_gate.check(
                state.step,
                state.ctx,
            )
            state.predicted_side_effects = predicted
            
            # Record predicted side-effects in STEP_START event metadata (for observability)
            # This allows tests and UI to verify that prediction phase occurred
            if allowed and predicted and hasattr(state, 'seq') and state.seq is not None:
                # Add predicted side-effects to STEP_START event if it was already recorded
                # (We can't modify the event directly, but we can record a debug event)
                # For now, predicted side-effects are stored in state.predicted_side_effects
                # and can be accessed via ExecutionState (internal) or verified via observation phase
                pass  # Prediction phase verified via absence of POLICY_DENIED + presence of SIDE_EFFECT_APPLIED
            
            if not allowed and gate_result:
                # Boundary gate denied - record and return
                state.policy_result = gate_result
                if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                    seq = services.recorder.next_seq()
                    self._record(
                        services,
                        build_policy_denied_event(
                            seq=seq,
                            run_context=state.run_ctx,
                            step_id=state.step.id,
                            tool=state.step.tool,
                            attempt=state.attempt,
                            policy_id="Side-Effect-Boundary",
                            rule_id="SE001",
                            rule_name="SideEffectBoundaryCheck",
                            reason=gate_result.reason or "Side-effect boundary crossed",
                        )
                    )
                
                return services.failure_builder.fail(
                    state=state,
                    error_code=gate_result.error_code or "SIDE_EFFECT_BOUNDARY_CROSSED",
                    message=gate_result.reason or "Side-effect boundary crossed",
                    phase=ExecutionPhase.POLICY,
                    suggestion=gate_result.suggestion,
                    remediation=gate_result.remediation,
                    details=gate_result.details,
                )
        
        # Phase 1.5: Process ownership check (for PROCESS_KILL operations)
        # This check runs after side-effect boundary but before semantic guard
        # to enforce PID ownership rules early in the policy chain
        if services.process_registry:
            ownership_result = self._check_process_ownership(state, services)
            if ownership_result is not None:
                # Ownership check denied - record and return
                state.policy_result = ownership_result
                if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                    seq = services.recorder.next_seq()
                    self._record(
                        services,
                        build_policy_denied_event(
                            seq=seq,
                            run_context=state.run_ctx,
                            step_id=state.step.id,
                            tool=state.step.tool,
                            attempt=state.attempt,
                            policy_id="Process-Ownership",
                            rule_id="PROC001",
                            rule_name="ProcessOwnershipCheck",
                            reason=ownership_result.reason or "PID not owned by this session",
                        )
                    )
                
                return services.failure_builder.fail(
                    state=state,
                    error_code=ownership_result.error_code or "PID_NOT_OWNED",
                    message=ownership_result.reason or "PID not owned by this session",
                    phase=ExecutionPhase.POLICY,
                    suggestion=ownership_result.suggestion,
                    details=ownership_result.details,
                )
        
        # Phase 2: Semantic guard (high-confidence malicious pattern detection)
        # Controlled by AnalysisConfig (see failcore.core.config.analysis)
        # Default: disabled (zero cost, zero behavior when disabled)
        # Only executes if enabled via config and guard instance is available
        if services.semantic_guard and services.semantic_guard.enabled:
            semantic_result = self._check_semantic_guard(state, services)
            if semantic_result is not None:
                # Semantic guard denied - convert to PolicyResult and record
                state.policy_result = semantic_result
                if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                    seq = services.recorder.next_seq()
                    self._record(
                        services,
                        build_policy_denied_event(
                            seq=seq,
                            run_context=state.run_ctx,
                            step_id=state.step.id,
                            tool=state.step.tool,
                            attempt=state.attempt,
                            policy_id="Semantic-Guard",
                            rule_id=semantic_result.details.get("rule_id", "SEM001") if isinstance(semantic_result.details, dict) else "SEM001",
                            rule_name="SemanticViolation",
                            reason=semantic_result.reason or "Semantic violation detected",
                        )
                    )
                
                return services.failure_builder.fail(
                    state=state,
                    error_code=semantic_result.error_code or "SEMANTIC_VIOLATION",
                    message=semantic_result.reason or "Semantic violation detected",
                    phase=ExecutionPhase.POLICY,  # Use POLICY phase (unified)
                    suggestion=semantic_result.suggestion,
                    remediation=semantic_result.remediation,
                    details=semantic_result.details,
                )
        
        # Phase 3: Taint tracking/DLP (data loss prevention)
        # Controlled by GuardConfig (per-run configuration)
        # Default: disabled (zero cost, zero behavior when disabled)
        if services.taint_engine and services.taint_store:
            taint_result = self._check_taint_dlp(state, services)
            if taint_result is not None:
                # Taint DLP denied or sanitized - handle accordingly
                if taint_result.get("action") == "block":
                    # DLP blocked - convert to PolicyResult and record
                    state.policy_result = taint_result["policy_result"]
                    if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                        seq = services.recorder.next_seq()
                        self._record(
                            services,
                            build_policy_denied_event(
                                seq=seq,
                                run_context=state.run_ctx,
                                step_id=state.step.id,
                                tool=state.step.tool,
                                attempt=state.attempt,
                                policy_id="DLP-Guard",
                                rule_id=taint_result.get("rule_id", "DLP001"),
                                rule_name="DataLeakagePrevention",
                                reason=taint_result["policy_result"].reason or "Data leakage prevented",
                            )
                        )
                    
                    return services.failure_builder.fail(
                        state=state,
                        error_code=taint_result["policy_result"].error_code or "DATA_LEAK_PREVENTED",
                        message=taint_result["policy_result"].reason or "Data leakage prevented",
                        phase=ExecutionPhase.POLICY,
                        suggestion=taint_result["policy_result"].suggestion,
                        remediation=taint_result["policy_result"].remediation,
                        details=taint_result["policy_result"].details,
                    )
                elif taint_result.get("action") == "sanitize":
                    # DLP sanitized params - update state and record event
                    sanitized_params = taint_result.get("sanitized_params")
                    if sanitized_params:
                        # Store original params for trace/audit
                        state.original_params = state.step.params.copy() if isinstance(state.step.params, dict) else state.step.params
                        state.sanitized_params = sanitized_params
                        
                        # Update step params (in-place update, don't rebuild Step object)
                        if isinstance(state.step.params, dict):
                            state.step.params.update(sanitized_params)
                        
                        # Record DLP sanitization event
                        if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                            seq = services.recorder.next_seq()
                            self._record_dlp_sanitized(services, state, seq, taint_result)
        
        # Phase 4: Main policy check using ValidationEngine
        if services.validation_engine:
            # Create validation context
            from ...validate import Context
            
            validation_context = Context(
                tool=state.step.tool,
                params=state.step.params,
                metadata={
                    "run_id": state.ctx.run_id,
                    "step_id": state.step.id,
                    "timestamp": state.started_at,
                }
            )
            
            try:
                # Use new ValidationEngine
                decisions = services.validation_engine.evaluate(validation_context)
                
                # Check for blocking decisions
                blocking_decisions = [d for d in decisions if d.is_blocking]
                
                if blocking_decisions:
                    # Policy denied - use first blocking decision
                    decision = blocking_decisions[0]
                    state.policy_result = (False, decision.message)
                    
                    # Record policy denied event
                    if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                        seq = services.recorder.next_seq()
                        self._record_policy_denied(services, state, seq, decision.message, decision.code)
                    
                    # Return StepResult to block execution
                    return services.failure_builder.fail(
                        state=state,
                        error_code=decision.code or "POLICY_DENIED",
                        message=decision.message,
                        phase=ExecutionPhase.POLICY,
                        suggestion=decision.evidence.get("suggestion") if decision.evidence else None,
                        details=decision.evidence or {},
                    )
                else:
                    # Policy allowed
                    state.policy_result = (True, "Validation passed")
                    
            except Exception as e:
                # Validation engine error - fail safe (allow but log error)
                state.policy_result = (True, f"Validation engine error: {e}")
        else:
            # No validation engine - allow by default
            state.policy_result = (True, "No validation engine configured")
        
        return None  # Continue to next stage
    
    def _check_process_ownership(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[Any]:
        """
        Check process ownership for PROCESS_KILL operations
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            PolicyResult if denied (PID not owned), None if allowed
        """
        from ...policy.process_ownership import ProcessOwnershipPolicy
        from ...policy.policy import PolicyResult
        
        # Create policy with process registry
        policy = ProcessOwnershipPolicy(process_registry=services.process_registry)
        
        # Check policy using new interface
        try:
            result = policy.allow(state.step, state.ctx)
            
            # Convert tuple to PolicyResult if needed
            if isinstance(result, tuple):
                allowed, reason = result
                if not allowed:
                    return PolicyResult.deny(
                        reason=reason,
                        error_code="PID_NOT_OWNED",
                    )
            elif isinstance(result, PolicyResult):
                if not result.allowed:
                    return result
        except AttributeError:
            # If policy doesn't have allow method, assume it's allowed
            # This handles cases where the policy interface is not fully implemented
            pass
        
        return None
    
    def _check_semantic_guard(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[Any]:  # Optional[PolicyResult]
        """
        Check semantic guard and return PolicyResult if violation detected
        
        Constraints:
        - Must return PolicyResult (not StepResult) - single interception point
        - Must not depend on RunContext internal structure - use stable context view
        - Module exceptions ≠ violations - must handle separately
        - Must return structured, explainable verdict
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            PolicyResult if violation detected, None if allowed
        """
        from ...policy.policy import PolicyResult
        from ...errors import FailCoreError
        
        # Construct stable context view (not RunContext internals)
        # Only expose stable, intentionally exposed fields
        semantic_context = {
            "tool": state.step.tool,
            "params": state.step.params,
            "run_id": state.ctx.run_id,
            "sandbox_root": str(state.ctx.sandbox_root) if hasattr(state.ctx, 'sandbox_root') else None,
            "cwd": state.ctx.cwd if hasattr(state.ctx, 'cwd') else None,
        }
        
        # Event emitter for semantic guard (optional, for audit)
        def emit_semantic_event(event_data: Dict[str, Any]) -> None:
            """Emit semantic check event (for audit, not for blocking)"""
            # Note: This is for observability only, not for blocking decisions
            # Semantic guard's verdict is what matters, not the event
            pass  # Could record to trace if needed, but not required for blocking
        
        try:
            # Call semantic guard (may raise FailCoreError if violation detected)
            # SemanticGuardMiddleware.on_call_start returns None if allowed, raises if blocked
            result = services.semantic_guard.on_call_start(
                tool_name=state.step.tool,
                params=state.step.params,
                context=semantic_context,
                emit=emit_semantic_event,
            )
            
            # If result is None, guard allowed execution
            if result is None:
                return None  # Allowed
            
            # If result is dict (warn/log), still allow but could log
            # Only explicit block should return PolicyResult
            return None  # For now, only explicit exceptions are blocks
            
        except FailCoreError as e:
            # Semantic violation detected - convert to PolicyResult
            # Extract structured information from error
            error_details = e.details if hasattr(e, 'details') and isinstance(e.details, dict) else {}
            
            # Build structured PolicyResult with explainable fields
            violation_details = error_details.get("violations", [])
            rule_id = None
            if violation_details and len(violation_details) > 0:
                rule_id = violation_details[0].get("rule_id") if isinstance(violation_details[0], dict) else None
            
            return PolicyResult.deny(
                reason=e.message or "Semantic violation detected",
                error_code=e.error_code or "SEMANTIC_VIOLATION",
                details={
                    "source": "semantic",  # Mark source for unified POLICY_DENIED event
                    "rule_id": rule_id,
                    "tool": state.step.tool,
                    "violations": violation_details,
                    "explanation": error_details.get("explanation"),
                    "evidence": error_details.get("evidence"),
                },
                suggestion=e.suggestion if hasattr(e, 'suggestion') else None,
                remediation=e.remediation if hasattr(e, 'remediation') else None,
            )
        
        except Exception as e:
            # Module exception (not a violation) - log but don't block
            # This ensures semantic module bugs don't cause false positives
            # Could record semantic_internal_error event, but don't block execution
            import logging
            logging.warning(
                f"Semantic guard internal error (not a violation): {type(e).__name__}: {e}",
                exc_info=True,
            )
            # Return None - allow execution (module exception ≠ violation)
            return None
    
    def _record(self, services: ExecutionServices, event: Any) -> None:
        """Record trace event (fail-safe)"""
        try:
            services.recorder.record(event)
        except Exception:
            pass
    
    def _check_taint_dlp(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[Dict[str, Any]]:
        """
        Check taint tracking/DLP and return result if action needed
        
        Constraints:
        - Must return PolicyResult for BLOCK/REQUIRE_APPROVAL (not StepResult)
        - Must handle module exceptions separately (not as violations)
        - Must return structured result with action type
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            Dict with keys:
                - action: "block" | "sanitize" | "require_approval" | None
                - policy_result: PolicyResult (if action is block/require_approval)
                - sanitized_params: Dict (if action is sanitize)
                - rule_id: str (rule identifier)
            None if allowed
        """
        from ...policy.policy import PolicyResult
        from ...errors import FailCoreError
        
        # Build stable context view (not RunContext internals)
        dlp_context = {
            "tool": state.step.tool,
            "params": state.step.params,
            "step_id": state.step.id,
            "run_id": state.ctx.run_id,
            "dependencies": [],  # TODO: Extract from trace or state if available
            "sandbox_root": str(state.ctx.sandbox_root) if hasattr(state.ctx, 'sandbox_root') else None,
            "cwd": state.ctx.cwd if hasattr(state.ctx, 'cwd') else None,
        }
        
        # Event emitter for DLP (optional, for audit)
        def emit_dlp_event(event_data: Dict[str, Any]) -> None:
            """Emit DLP event (for audit, not for blocking)"""
            pass  # Could record to trace if needed
        
        try:
            # Call DLP middleware on_call_start
            # Returns: None (allowed), Dict (sanitized params), or raises FailCoreError (blocked)
            result = services.taint_engine.on_call_start(
                tool_name=state.step.tool,
                params=state.step.params,
                context=dlp_context,
                emit=emit_dlp_event,
            )
            
            # If result is None, guard allowed execution
            if result is None:
                return None  # Allowed
            
            # If result is Dict (sanitized params), return sanitize action
            if isinstance(result, dict):
                return {
                    "action": "sanitize",
                    "sanitized_params": result,
                    "rule_id": "DLP_SANITIZE",
                }
            
            # Should not reach here (on_call_start should return None or Dict or raise)
            return None
            
        except FailCoreError as e:
            # DLP violation detected - convert to PolicyResult
            error_details = e.details if hasattr(e, 'details') and isinstance(e.details, dict) else {}
            
            # Determine action from error code
            action = "block"
            if e.error_code == "APPROVAL_REQUIRED":
                action = "require_approval"
            
            # Build structured PolicyResult
            return {
                "action": action,
                "policy_result": PolicyResult.deny(
                    reason=e.message or "Data leakage prevented",
                    error_code=e.error_code or "DATA_LEAK_PREVENTED",
                    details={
                        "source": "taint",  # Mark source for unified POLICY_DENIED event
                        "tool": state.step.tool,
                        "sensitivity": error_details.get("sensitivity"),
                        "sources": error_details.get("sources"),
                        "taint_count": error_details.get("taint_count"),
                    },
                    suggestion=e.suggestion if hasattr(e, 'suggestion') else None,
                    remediation=e.remediation if hasattr(e, 'remediation') else None,
                ),
                "rule_id": error_details.get("rule_id", "DLP001"),
            }
        
        except Exception as e:
            # Module exception (not a violation) - log but don't block
            # This ensures DLP module bugs don't cause false positives
            import logging
            logging.warning(
                f"DLP middleware internal error (not a violation): {type(e).__name__}: {e}",
                exc_info=True,
            )
            # Return None - allow execution (module exception ≠ violation)
            return None
    
    def _record_dlp_sanitized(
        self,
        services: ExecutionServices,
        state: ExecutionState,
        seq: int,
        taint_result: Dict[str, Any],
    ) -> None:
        """Record DLP sanitization event"""
        event = TraceEvent(
            schema="failcore.trace.v0.1.3",
            seq=seq,
            ts=utc_now_iso(),
            level=LogLevel.INFO,
            event={
                "type": EventType.RESULT.value,  # Policy decision recorded in RESULT event
                "severity": "warn",
                "step": {
                    "id": state.step.id,
                    "tool": state.step.tool,
                    "attempt": state.attempt,
                },
                "data": {
                    "policy": {
                        "policy_id": "DLP-Guard",
                        "rule_id": taint_result.get("rule_id", "DLP_SANITIZE"),
                        "action": "sanitize",
                        "reason": "Data sanitized before execution",
                    },
                    "sanitization": {
                        "original_params": state.original_params,
                        "sanitized_params": state.sanitized_params,
                        "fields_sanitized": list(state.sanitized_params.keys()) if isinstance(state.sanitized_params, dict) else [],
                    },
                },
            },
            run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
        )
        
        try:
            services.recorder.record(event)
        except Exception:
            # Don't fail execution if event recording fails
            pass
    
    def _record_policy_denied(
        self,
        services: ExecutionServices,
        state: ExecutionState,
        seq: int,
        reason: str,
        error_code: str,
    ) -> None:
        """Record policy denied event"""
        event = TraceEvent(
            schema="failcore.trace.v0.1.3",
            seq=seq,
            ts=utc_now_iso(),
            level=LogLevel.WARN,
            event={
                "type": EventType.POLICY_DENIED.value,
                "severity": "error",
                "step": {
                    "id": state.step.id,
                    "tool": state.step.tool,
                    "attempt": state.attempt,
                },
                "data": {
                    "policy": {
                        "policy_id": "ValidationEngine",
                        "rule_id": error_code,
                        "action": "block",
                        "reason": reason,
                    },
                },
            },
            run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
        )
        
        try:
            services.recorder.record(event)
        except Exception:
            pass  # Ignore recording errors