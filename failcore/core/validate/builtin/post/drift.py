"""
Drift Validator (Post-Run)

Post-run validator that detects parameter drift in execution traces.

This validator:
- Processes trace after run completion
- Detects parameter drift from baseline
- Identifies inflection points (behavior changes)
- Outputs drift score and annotations
- Writes to audit report

NOTE: This is a post-run validator, not a runtime gate.
It should be called after execution completes, with the full trace.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, RiskLevel
from failcore.core.replay.drift import (
    compute_drift,
    DriftResult,
    DriftPoint,
    InflectionPoint,
)


class PostRunDriftValidator(BaseValidator):
    """
    Post-Run Drift Validator
    
    Analyzes execution trace for parameter drift.
    
    This validator:
    - Accepts trace path or events list in Context.state
    - Computes drift analysis
    - Emits decisions for significant drift/inflection points
    - Provides drift score and annotations
    
    Usage:
    - Set Context.state["trace_path"] or Context.state["trace_events"]
    - Call evaluate() after run completion
    - Decisions contain drift analysis results
    """
    
    @property
    def id(self) -> str:
        return "post_run_drift"
    
    @property
    def domain(self) -> str:
        return "audit"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for drift validator configuration"""
        return {
            "type": "object",
            "properties": {
                "drift_threshold": {
                    "type": "number",
                    "description": "Minimum drift score to report (default: 0.1)",
                    "default": 0.1,
                },
                "report_inflection_points": {
                    "type": "boolean",
                    "description": "Report inflection points as decisions",
                    "default": True,
                },
                "report_all_drift": {
                    "type": "boolean",
                    "description": "Report all drift points (not just inflection)",
                    "default": False,
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        """Default drift validator configuration"""
        return {
            "drift_threshold": 0.1,
            "report_inflection_points": True,
            "report_all_drift": False,
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate drift validation (post-run)
        
        Args:
            context: Validation context (should contain trace_path or trace_events in state)
            config: Validator configuration
            
        Returns:
            List of Decision objects for drift/inflection points
        """
        decisions: List[Decision] = []
        
        # Get configuration
        cfg = self._get_config(config)
        
        # Get trace from context state (standardized input)
        state = context.state or {}
        
        # Priority: trace_source enum determines which input to use
        trace_source = state.get("trace_source", "auto")  # "path", "events", "auto"
        
        trace_path = None
        trace_events = None
        
        if trace_source == "path" or (trace_source == "auto" and "trace_path" in state):
            trace_path = state.get("trace_path")
        elif trace_source == "events" or (trace_source == "auto" and "trace_events" in state):
            trace_events = state.get("trace_events")
        else:
            # Fallback: try both
            trace_path = state.get("trace_path")
            trace_events = state.get("trace_events")
        
        if not trace_path and not trace_events:
            # No trace available, return empty
            return decisions
        
        # Check trace completeness
        trace_completeness = "unknown"
        if trace_path:
            trace_completeness = "path_provided"
        elif trace_events:
            # Check if events look complete
            if isinstance(trace_events, list):
                # Simple heuristic: check for start/end markers or expected structure
                has_start = any("start" in str(e).lower() or "begin" in str(e).lower() for e in trace_events[:5])
                has_end = any("end" in str(e).lower() or "complete" in str(e).lower() for e in trace_events[-5:])
                if has_start and has_end:
                    trace_completeness = "complete"
                elif has_start:
                    trace_completeness = "partial"
                else:
                    trace_completeness = "unknown"
            else:
                trace_completeness = "invalid"
        
        # Compute drift
        try:
            drift_result = compute_drift(
                trace_path_or_events=trace_path or trace_events,
                config=None,  # Use default drift config
            )
        except Exception as e:
            # Drift computation failed
            return [
                Decision.warn(
                    code="FC_DRIFT_COMPUTATION_ERROR",
                    validator_id=self.id,
                    message=f"Drift computation failed: {e}",
                    evidence={"error": str(e)},
                    risk_level=RiskLevel.LOW,
                )
            ]
        
        # Process drift points
        drift_threshold = cfg.get("drift_threshold", 0.1)
        
        # Report inflection points (significant behavior changes)
        if cfg.get("report_inflection_points", True):
            for inflection in drift_result.inflection_points:
                decision = self._inflection_to_decision(
                    inflection=inflection,
                    drift_result=drift_result,
                    context=context,
                    trace_metadata=trace_metadata,
                )
                decisions.append(decision)
        
        # Report high drift points (if enabled)
        if cfg.get("report_all_drift", False):
            for drift_point in drift_result.drift_points:
                if drift_point.drift_delta >= drift_threshold:
                    decision = self._drift_point_to_decision(
                        drift_point=drift_point,
                        context=context,
                    )
                    decisions.append(decision)
        
        # Add summary decision if no specific points reported
        if not decisions and drift_result.drift_points:
            max_drift = max(
                (dp.drift_cumulative for dp in drift_result.drift_points),
                default=0.0,
            )
            if max_drift >= drift_threshold:
                decisions.append(
                    Decision.warn(
                        code="FC_DRIFT_SUMMARY",
                        validator_id=self.id,
                        message=f"Parameter drift detected: max cumulative drift = {max_drift:.2f}",
                        evidence={
                            "max_drift": max_drift,
                            "total_snapshots": len(drift_result.snapshots),
                            "total_drift_points": len(drift_result.drift_points),
                            "inflection_points": len(drift_result.inflection_points),
                        },
                        risk_level=RiskLevel.MEDIUM,
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                )
        
        return decisions
    
    def _inflection_to_decision(
        self,
        inflection: InflectionPoint,
        drift_result: DriftResult,
        context: Context,
        trace_metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """Convert inflection point to Decision"""
        # Find corresponding drift point
        drift_point = None
        for dp in drift_result.drift_points:
            if dp.seq == inflection.seq:
                drift_point = dp
                break
        
        # Build evidence
        evidence: Dict[str, Any] = {
            "seq": inflection.seq,
            "tool": inflection.tool,
            "timestamp": inflection.ts,
            "drift_delta": inflection.drift_delta,
            "prev_drift_delta": inflection.prev_drift_delta,
            "reason": inflection.reason,
        }
        
        # Add trace metadata
        if trace_metadata:
            evidence.update(trace_metadata)
        
        if drift_point and drift_point.top_changes:
            evidence["top_changes"] = [
                {
                    "field_path": change.field_path,
                    "change_type": change.change_type,
                    "severity": change.severity,
                    "reason": change.reason,
                }
                for change in drift_point.top_changes[:3]  # Top 3 changes
            ]
        
        # Determine risk level based on drift delta
        risk_level = RiskLevel.MEDIUM
        if inflection.drift_delta >= 1.0:
            risk_level = RiskLevel.HIGH
        elif inflection.drift_delta >= 0.5:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        return Decision.warn(
            code="FC_DRIFT_INFLECTION_POINT",
            validator_id=self.id,
            message=(
                f"Drift inflection point detected at step {inflection.seq} "
                f"({inflection.tool}): {inflection.reason}"
            ),
            evidence=evidence,
            risk_level=risk_level,
            tool=inflection.tool,
            step_id=None,  # InflectionPoint doesn't have step_id
            remediation=(
                f"Review parameter changes at step {inflection.seq}. "
                f"Behavior drift detected: {inflection.reason}"
            ),
        )
    
    def _drift_point_to_decision(
        self,
        drift_point: DriftPoint,
        context: Context,
    ) -> Decision:
        """Convert drift point to Decision"""
        evidence: Dict[str, Any] = {
            "seq": drift_point.seq,
            "tool": drift_point.tool,
            "timestamp": drift_point.ts,
            "drift_delta": drift_point.drift_delta,
            "drift_cumulative": drift_point.drift_cumulative,
        }
        
        if drift_point.top_changes:
            evidence["top_changes"] = [
                {
                    "field_path": change.field_path,
                    "change_type": change.change_type,
                    "severity": change.severity,
                }
                for change in drift_point.top_changes[:3]
            ]
        
        return Decision.warn(
            code="FC_DRIFT_PARAMETER_CHANGE",
            validator_id=self.id,
            message=(
                f"Parameter drift detected at step {drift_point.seq} "
                f"({drift_point.tool}): delta={drift_point.drift_delta:.2f}"
            ),
            evidence=evidence,
            risk_level=RiskLevel.MEDIUM,
            tool=drift_point.tool,
            step_id=drift_point.step_id,
        )
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default


__all__ = ["PostRunDriftValidator"]
