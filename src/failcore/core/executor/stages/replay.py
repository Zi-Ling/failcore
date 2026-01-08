# failcore/core/executor/stages/replay.py
"""
Replay Stage - replay decision and event recording (adopts suggestion 2)

This stage handles replay decisions and records trace events.
The ReplayExecutionHook only makes decisions; this stage records events.
"""

from typing import Optional, Any

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult, StepStatus, StepError
from failcore.core.types.step import utc_now_iso
from ...trace import (
    build_replay_hit_event,
    build_replay_miss_event,
    build_replay_policy_diff_event,
    build_replay_injected_event,
)
from ...replay.execution import ReplayHitType


class ReplayStage:
    """Stage 5: Replay hook (before tool execution)"""
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Execute replay hook and record events
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult if replay HIT (injected), None otherwise
        
        Note:
            - Records replay events based on ReplayDecision (adopts suggestion 2)
            - Sets state.replay_decision
        """
        if not services.replay_hook:
            return None  # Replay disabled
        
        # Get policy result for replay hook
        policy_result = None
        if state.policy_result:
            from ...policy.policy import PolicyResult
            if isinstance(state.policy_result, PolicyResult):
                policy_result = (state.policy_result.allowed, state.policy_result.reason)
            elif isinstance(state.policy_result, tuple):
                policy_result = state.policy_result
        
        # Execute replay hook (returns ReplayDecision)
        replay_decision = services.replay_hook.execute(
            step_id=state.step.id,
            tool=state.step.tool,
            params=state.step.params,
            policy_result=policy_result,
        )
        
        if not replay_decision:
            return None  # Replay disabled
        
        state.replay_decision = replay_decision
        
        # Record replay events based on decision (adopts suggestion 2)
        if hasattr(services.recorder, 'next_seq') and state.seq is not None:
            seq = services.recorder.next_seq()
            
            if replay_decision.hit_type == ReplayHitType.HIT:
                # Lightweight drift detection: compare current params with baseline step
                # (Must be called before recording event to populate diff_details)
                self._detect_replay_drift(state, services, replay_decision)
                
                # Record HIT event (with diff_details if present)
                hit_event = build_replay_hit_event(
                    seq=seq,
                    run_context=state.run_ctx,
                    step_id=state.step.id,
                    tool=state.step.tool,
                    attempt=state.attempt,
                    mode=services.replayer.mode.value if services.replayer else "mock",
                    fingerprint_id=replay_decision.fingerprint.get("id", "") if replay_decision.fingerprint else "",
                    matched_step_id=replay_decision.match_info.matched_step.get("step_id", "unknown") if replay_decision.match_info and replay_decision.match_info.matched_step else "unknown",
                    source_trace=services.replayer.trace_path if services.replayer else "",
                )
                
                # Add diff_details (including params_drift) to event if present
                if replay_decision.diff_details:
                    hit_event.event["data"]["diff_details"] = replay_decision.diff_details
                
                self._record(services, hit_event)
                
                # Check for diffs
                if replay_decision.diff_details:
                    policy_diff = replay_decision.diff_details.get("policy")
                    if policy_diff:
                        seq = services.recorder.next_seq()
                        self._record(
                            services,
                            build_replay_policy_diff_event(
                                seq=seq,
                                run_context=state.run_ctx,
                                step_id=state.step.id,
                                tool=state.step.tool,
                                attempt=state.attempt,
                                historical_decision=policy_diff.get("historical", ""),
                                current_decision=policy_diff.get("current", ""),
                                historical_reason=policy_diff.get("historical_reason"),
                                current_reason=policy_diff.get("current_reason"),
                            )
                        )
                
                # If mock mode, inject output
                if services.replayer and services.replayer.mode.value == "mock" and replay_decision.injected:
                    seq = services.recorder.next_seq()
                    output_kind = replay_decision.step_result.output.kind.value if replay_decision.step_result and replay_decision.step_result.output else "none"
                    self._record(
                        services,
                        build_replay_injected_event(
                            seq=seq,
                            run_context=state.run_ctx,
                            step_id=state.step.id,
                            tool=state.step.tool,
                            attempt=state.attempt,
                            fingerprint_id=replay_decision.fingerprint.get("id", "") if replay_decision.fingerprint else "",
                            output_kind=output_kind,
                        )
                    )
                    
                    # Return the injected result
                    return replay_decision.step_result
            
            elif replay_decision.hit_type == ReplayHitType.MISS:
                # Record MISS
                self._record(
                    services,
                    build_replay_miss_event(
                        seq=seq,
                        run_context=state.run_ctx,
                        step_id=state.step.id,
                        tool=state.step.tool,
                        attempt=state.attempt,
                        mode=services.replayer.mode.value if services.replayer else "mock",
                        fingerprint_id=replay_decision.fingerprint.get("id") if replay_decision.fingerprint else None,
                        reason=replay_decision.message or "No matching fingerprint",
                    )
                )
                
                # MISS: stop replay, don't execute tool (if report mode)
                if services.replayer and services.replayer.mode.value == "report":
                    return StepResult(
                        step_id=state.step.id,
                        tool=state.step.tool,
                        status=StepStatus.FAIL,
                        started_at=utc_now_iso(),
                        finished_at=utc_now_iso(),
                        duration_ms=0,
                        output=None,
                        error=StepError(
                            error_code="REPLAY_MISS",
                            message=f"Replay miss: {replay_decision.message}",
                        ),
                        meta={"replay": True, "hit_type": "MISS"},
                    )
        
        return None  # Continue to next stage
    
    def _detect_replay_drift(
        self,
        state: ExecutionState,
        services: ExecutionServices,
        replay_decision: Any,
    ) -> None:
        """
        Lightweight drift detection for replay HIT
        
        Compares current step params with baseline step params.
        Only detects drift for this specific step, not the entire trace.
        
        Args:
            state: Execution state
            services: Execution services
            replay_decision: Replay decision containing match info
        """
        if not replay_decision.match_info or not replay_decision.match_info.matched_step:
            return  # No baseline step to compare
        
        try:
            from ...replay.drift.rules import detect_drift
            from ...replay.drift.config import get_default_config
            
            # Get baseline params from matched step
            matched_step = replay_decision.match_info.matched_step
            baseline_params = matched_step.get("params") or matched_step.get("input", {}).get("raw", {})
            
            if not baseline_params:
                return  # No baseline params available
            
            # Detect drift between baseline and current params
            config = get_default_config()
            drift_changes = detect_drift(
                baseline_params=baseline_params,
                current_params=state.step.params,
                tool_name=state.step.tool,
                config=config,
            )
            
            # If drift detected, add to diff_details (aligned with existing structure)
            # Structure matches existing diff_details["policy"] pattern
            if drift_changes:
                if not replay_decision.diff_details:
                    replay_decision.diff_details = {}
                
                # Calculate drift delta (sum of change weights for quick reference)
                from ...replay.drift.config import get_default_config
                drift_config = get_default_config()
                drift_delta = sum(
                    drift_config.drift_weight_value_changed if c.change_type == "value_changed"
                    else drift_config.drift_weight_magnitude_changed if c.change_type == "magnitude_changed"
                    else drift_config.drift_weight_domain_changed if c.change_type == "domain_changed"
                    else 1.0
                    for c in drift_changes
                )
                
                replay_decision.diff_details["params_drift"] = {
                    "drift": True,  # Boolean flag for quick check
                    "delta": drift_delta,  # Total drift score
                    "changes": [
                        {
                            "field_path": c.field_path,
                            "baseline_value": c.baseline_value,
                            "current_value": c.current_value,
                            "change_type": c.change_type,
                            "severity": c.severity,
                            "reason": c.reason,
                        }
                        for c in drift_changes[:5]  # Top 5 changes
                    ],
                    "total_changes": len(drift_changes),
                }
                # Note: This does NOT trigger a separate REPLAY_DRIFT_DETECTED event.
                # It's included in diff_details and can be accessed via existing diff reporting.
        except Exception:
            # Don't fail replay if drift detection fails
            pass
    
    def _record(self, services: ExecutionServices, event: Any) -> None:
        """Record trace event (fail-safe)"""
        try:
            services.recorder.record(event)
        except Exception:
            pass
