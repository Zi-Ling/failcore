# failcore/web/services/replay_service.py
"""
Replay Service - Trace → Frames conversion

Converts trace.jsonl events into structured frames for replay viewer.
This service only handles "fact reconstruction", not UI logic or anomaly detection.
"""

from typing import Dict, Any, List, Optional
from collections import defaultdict

from .replay_schema import StepFrame, IncidentTape, RunMeta, CostBudget, CostPoint, IncidentEvent
from .repos.trace_repo import TraceRepo
from .cost_service import get_cost_service
from .replay_diff import diff_args
from .decision_narrator import get_decision_narrator
from .anomaly import get_anomaly_engine
from .actions_service import get_actions_service


class ReplayService:
    """
    Service for converting trace events to replay frames
    
    Responsibilities:
    - Parse trace.jsonl
    - Merge STEP_START + STEP_END into frames
    - Extract tool arguments and results
    - Build incident tape structure
    
    Does NOT:
    - Detect anomalies (use AnomalyEngine)
    - Make decisions (use PolicyEngine)
    - Format for UI (use templates/JS)
    """
    
    def __init__(self, trace_repo: Optional[TraceRepo] = None):
        """
        Initialize replay service
        
        Args:
            trace_repo: Optional trace repository (creates default if None)
        """
        self.trace_repo = trace_repo or TraceRepo()
        self.cost_service = get_cost_service()
        self.actions_service = get_actions_service()
    
    def load_trace(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Load trace events for a run
        
        Args:
            run_id: Run ID
        
        Returns:
            List of trace events
        """
        return self.trace_repo.load_trace_events(run_id)
    
    def merge_step_events(self, events: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """
        Merge STEP_START and STEP_END events by seq
        
        Args:
            events: List of trace events
        
        Returns:
            Dictionary mapping seq -> merged step data
        """
        steps = defaultdict(dict)
        
        for event in events:
            evt = event.get("event", {})
            evt_type = evt.get("type")
            seq = event.get("seq", 0)
            
            if evt_type == "STEP_START":
                step = evt.get("step", {})
                steps[seq]["seq"] = seq
                steps[seq]["ts_start"] = event.get("ts", "")
                steps[seq]["tool"] = step.get("tool", "")
                steps[seq]["args_raw"] = step.get("params", {})
                steps[seq]["args"] = step.get("params", {})  # Normalized args (same as raw for now)
            
            elif evt_type == "STEP_END":
                data = evt.get("data", {})
                result = data.get("result", {})
                step = evt.get("step", {})
                
                steps[seq]["seq"] = seq
                steps[seq]["ts_end"] = event.get("ts", "")
                steps[seq]["status"] = result.get("status", "UNKNOWN")
                steps[seq]["result_raw"] = result.get("output")
                
                # Extract result summary
                output = result.get("output")
                if isinstance(output, str):
                    steps[seq]["result_summary"] = output[:200] + "..." if len(output) > 200 else output
                elif isinstance(output, dict):
                    steps[seq]["result_summary"] = str(output).replace("{", "").replace("}", "")[:200]
                else:
                    steps[seq]["result_summary"] = str(output)[:200] if output else None
                
                # Extract error info
                error = result.get("error")
                if error:
                    steps[seq]["error_code"] = error.get("code")
                    steps[seq]["error_message"] = error.get("message")
                    # Extract side-effect crossing info if present
                    error_type = error.get("type")
                    if error_type == "SIDE_EFFECT_BOUNDARY_CROSSED":
                        details = error.get("details", {})
                        steps[seq]["side_effect_crossing"] = {
                            "crossing_type": details.get("crossing_type"),
                            "observed_category": details.get("observed_category"),
                            "target": details.get("target"),
                            "tool": details.get("tool"),
                            "step_id": details.get("step_id"),
                            "step_seq": details.get("step_seq"),
                            "allowed_categories": details.get("allowed_categories", []),
                        }
                
                # Extract metrics
                metrics = data.get("metrics", {})
                cost_metrics = metrics.get("cost")
                if cost_metrics:
                    steps[seq]["metrics"] = cost_metrics
        
        return dict(steps)
    
    def build_frames(self, run_id: str, events: Optional[List[Dict[str, Any]]] = None) -> List[StepFrame]:
        """
        Build frames from trace events
        
        Args:
            run_id: Run ID
            events: Optional pre-loaded events (to avoid double loading)
        
        Returns:
            List of StepFrame objects (ordered by seq)
        """
        if events is None:
            events = self.load_trace(run_id)
        merged_steps = self.merge_step_events(events)
        
        frames = []
        prev_frame_by_tool = {}  # Track previous frame for each tool (for diff)
        
        for seq in sorted(merged_steps.keys()):
            step_data = merged_steps[seq]
            tool = step_data.get("tool", "")
            args = step_data.get("args", {})
            
            # Compute args_diff with previous frame of same tool
            prev_args = None
            if tool in prev_frame_by_tool:
                prev_frame = prev_frame_by_tool[tool]
                prev_args = prev_frame.args
            
            args_diff = diff_args(prev_args, args) if prev_args is not None or tool in prev_frame_by_tool else None
            
            # Detect anomalies
            anomaly_engine = get_anomaly_engine()
            anomalies = anomaly_engine.analyze(tool, args, metadata=None)
            
            # Get tool metadata (risk_level, side_effect)
            tool_metadata = self.actions_service.get_tool_metadata(tool)
            
            # Extract policy context and evidence from trace events
            policy_context = self._extract_policy_context(events, seq)
            evidence = self._extract_evidence(events, seq)
            
            # Generate decision narrative
            decision_narrator = get_decision_narrator()
            # Create temporary frame for narration (anomalies already computed)
            temp_frame = StepFrame(
                seq=seq,
                ts_start=step_data.get("ts_start", ""),
                tool=tool,
                status=step_data.get("status", "PENDING"),
                args=args,
                anomalies=anomalies,
                error_code=step_data.get("error_code"),
                metrics=step_data.get("metrics"),
                evidence=evidence,
            )
            decision = decision_narrator.narrate(temp_frame, policy_context=policy_context)
            
            # Add tool metadata to frame (for UI display)
            frame_extras = {}
            if tool_metadata:
                frame_extras["tool_metadata"] = tool_metadata
            
            frame = StepFrame(
                seq=step_data.get("seq", seq),
                ts_start=step_data.get("ts_start", ""),
                ts_end=step_data.get("ts_end"),
                tool=tool,
                status=step_data.get("status", "PENDING"),
                args=args,
                args_raw=step_data.get("args_raw"),
                args_diff=args_diff,
                result_summary=step_data.get("result_summary"),
                result_raw=step_data.get("result_raw"),
                anomalies=anomalies,
                decision=decision,
                metrics=step_data.get("metrics"),
                evidence=evidence,
                error_code=step_data.get("error_code"),
                error_message=step_data.get("error_message"),
            )
            
            # Add metadata to frame dict (not in schema, but needed for UI)
            frame_dict = frame.to_dict()
            if tool_metadata:
                frame_dict["tool_metadata"] = tool_metadata
            # Store in a way that can be accessed in to_dict
            frame._tool_metadata = tool_metadata
            frames.append(frame)
            
            # Update previous frame for this tool
            prev_frame_by_tool[tool] = frame
        
        return frames
    
    def build_incident_tape(self, run_id: str) -> IncidentTape:
        """
        Build complete incident tape for a run
        
        Args:
            run_id: Run ID
        
        Returns:
            IncidentTape object
        """
        # Build frames
        frames = self.build_frames(run_id)
        
        # Extract run metadata
        events = self.load_trace(run_id)
        meta = self._extract_meta(run_id, events)
        
        # Extract events (blocked steps, etc.)
        incident_events = self._extract_events(frames)
        
        # Compute drift and inject into frames
        self._inject_drift_into_frames(frames, events)
        
        # Inject side-effect crossings into frames
        self._inject_side_effect_crossings(frames, events)
        
        # Load cost data
        cost_data = self.cost_service.get_run_cost(run_id)
        budget = None
        if cost_data.get("budget"):
            budget_dict = cost_data["budget"]
            budget = CostBudget(
                max_cost_usd=budget_dict.get("max_cost_usd"),
                max_tokens=budget_dict.get("max_tokens"),
                max_usd_per_minute=budget_dict.get("max_usd_per_minute"),
            )
        
        cost_curve = []
        for point in cost_data.get("points", []):
            cost_curve.append(CostPoint(
                seq=point.get("seq", 0),
                ts=point.get("ts", ""),
                delta_cost_usd=point.get("delta_cost_usd", 0.0),
                cum_cost_usd=point.get("cum_cost_usd", 0.0),
                delta_tokens=point.get("delta_tokens", 0),
                cum_tokens=point.get("cum_tokens", 0),
                status=point.get("status", "OK"),
                tool=point.get("tool", ""),
                error_code=point.get("error_code"),
            ))
        
        return IncidentTape(
            run_id=run_id,
            meta=meta,
            frames=frames,
            events=incident_events,
            budget=budget,
            cost_curve=cost_curve,
        )
    
    def _inject_drift_into_frames(
        self,
        frames: List[StepFrame],
        events: List[Dict[str, Any]],
    ) -> None:
        """
        Compute drift and inject into frames
        
        Args:
            frames: List of StepFrame objects (modified in place)
            events: List of trace events
        """
        try:
            from failcore.core.replay.drift import compute_drift, annotate_drift
            
            # Compute drift from events
            drift_result = compute_drift(events)
            
            # Create lookup maps
            drift_by_seq = {dp.seq: dp for dp in drift_result.drift_points}
            
            # Inject drift data into frames
            for frame in frames:
                drift_point = drift_by_seq.get(frame.seq)
                if drift_point and drift_point.drift_delta > 0:
                    # Add drift data
                    frame.drift = {
                        "delta": drift_point.drift_delta,
                        "cumulative": drift_point.drift_cumulative,
                    }
                    
                    # Generate annotation for this drift point
                    annotation = annotate_drift(
                        drift_point,
                        drift_result.inflection_points,
                    )
                    if annotation:
                        frame.drift_annotations = [annotation.to_dict()]
                    else:
                        frame.drift_annotations = []
                else:
                    # No drift for this frame
                    frame.drift = None
                    frame.drift_annotations = []
        except Exception as e:
            # If drift computation fails, continue without drift data
            # This ensures replay still works even if drift engine has issues
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to compute drift: {e}", exc_info=True)
            # Set drift to None for all frames if computation fails
            for frame in frames:
                frame.drift = None
                frame.drift_annotations = []
    
    def _inject_side_effect_crossings(
        self,
        frames: List[StepFrame],
        events: List[Dict[str, Any]],
    ) -> None:
        """
        Extract side-effect crossings from trace events and inject into frames
        
        Args:
            frames: List of StepFrame objects (modified in place)
            events: List of trace events
        """
        try:
            # Extract crossings from events
            crossings_by_seq = {}
            for event in events:
                evt = event.get("event", {})
                evt_type = evt.get("type")
                seq = event.get("seq", 0)
                
                if evt_type == "STEP_END":
                    data = evt.get("data", {})
                    result = data.get("result", {})
                    error = result.get("error")
                    if error and error.get("type") == "SIDE_EFFECT_BOUNDARY_CROSSED":
                        details = error.get("details", {})
                        crossings_by_seq[seq] = {
                            "crossing_type": details.get("crossing_type"),
                            "observed_category": details.get("observed_category"),
                            "target": details.get("target"),
                            "tool": details.get("tool"),
                            "step_id": details.get("step_id"),
                            "step_seq": details.get("step_seq"),
                            "allowed_categories": details.get("allowed_categories", []),
                        }
            
            # Inject crossings into frames
            for frame in frames:
                crossing_data = crossings_by_seq.get(frame.seq)
                if crossing_data:
                    # Create annotation from crossing data
                    annotation_dict = {
                        "badge": "BOUNDARY CROSSED",
                        "severity": "high",
                        "crossing_type": crossing_data.get("crossing_type", ""),
                        "target": crossing_data.get("target"),
                        "tool": crossing_data.get("tool"),
                        "step_seq": frame.seq,
                        "allowed_categories": crossing_data.get("allowed_categories", []),
                    }
                    
                    # Generate summary
                    crossing_type = crossing_data.get("crossing_type", "unknown")
                    target_str = f" -> {crossing_data.get('target')}" if crossing_data.get("target") else ""
                    allowed_str = ", ".join(crossing_data.get("allowed_categories", [])) or "none"
                    annotation_dict["summary"] = f"Boundary crossed: {crossing_type}{target_str}. Allowed: {allowed_str}"
                    
                    frame.side_effect_crossings = [annotation_dict]
                else:
                    frame.side_effect_crossings = []
        except Exception as e:
            # If crossing extraction fails, continue without crossing data
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to extract side-effect crossings: {e}", exc_info=True)
            # Set crossings to empty for all frames if extraction fails
            for frame in frames:
                frame.side_effect_crossings = []
    
    def get_incident_tape(self, run_id: str) -> IncidentTape:
        """
        Get incident tape for a run (alias for build_incident_tape)
        
        This method provides a consistent API interface for retrieving incident tape data.
        
        Args:
            run_id: Run ID
        
        Returns:
            IncidentTape object
        """
        return self.build_incident_tape(run_id)
    
    def _extract_meta(self, run_id: str, events: List[Dict[str, Any]]) -> RunMeta:
        """Extract run metadata from trace events"""
        # Try to find RUN_START event
        for event in events:
            evt = event.get("event", {})
            if evt.get("type") == "RUN_START":
                run_data = evt.get("data", {})
                run_info = run_data.get("run", {})
                return RunMeta(
                    run_id=run_id,
                    command=run_info.get("command"),
                    workspace=run_info.get("workspace"),
                    sandbox_root=run_info.get("sandbox_root"),
                    created_at=event.get("ts"),
                    status="completed",  # Default, could be improved
                )
        
        # Fallback: parse from run_id
        if "_" in run_id:
            parts = run_id.split("_", 1)
            return RunMeta(run_id=run_id, command=parts[1] if len(parts) > 1 else None)
        
        return RunMeta(run_id=run_id)
    
    def _extract_events(self, frames: List[StepFrame]) -> List[IncidentEvent]:
        """Extract incident events from frames"""
        events = []
        
        for frame in frames:
            if frame.status in ("BLOCKED", "blocked") or frame.error_code:
                event_type = "blocked"
                reason = f"Step {frame.seq} blocked"
                
                if frame.error_code:
                    if "BUDGET" in frame.error_code:
                        event_type = "budget_exceeded"
                        reason = f"Step {frame.seq} blocked: Budget exceeded ({frame.error_code})"
                    elif "BURN_RATE" in frame.error_code:
                        event_type = "burn_rate_exceeded"
                        reason = f"Step {frame.seq} blocked: Burn rate exceeded ({frame.error_code})"
                    else:
                        reason = f"Step {frame.seq} blocked: {frame.error_code}"
                
                events.append(IncidentEvent(
                    type=event_type,
                    seq=frame.seq,
                    ts=frame.ts_end or frame.ts_start,
                    reason=reason,
                    error_code=frame.error_code,
                ))
        
        return events
    
    def _extract_policy_context(self, events: List[Dict[str, Any]], seq: int) -> Optional[Dict[str, Any]]:
        """Extract policy context from trace events for a specific step"""
        for event in events:
            if event.get("seq") == seq:
                evt = event.get("event", {})
                evt_type = evt.get("type")
                
                if evt_type == "POLICY_DENIED":
                    data = evt.get("data", {})
                    policy = data.get("policy", {})
                    return {
                        "rule_id": policy.get("rule_id"),
                        "rule_name": policy.get("rule_name"),
                        "policy_id": policy.get("policy_id"),
                        "reason": policy.get("reason"),
                    }
        
        return None
    
    def _extract_evidence(self, events: List[Dict[str, Any]], seq: int) -> List[Dict[str, Any]]:
        """Extract evidence from trace events for a specific step"""
        evidence = []
        
        for idx, event in enumerate(events):
            event_seq = event.get("seq", 0)
            if event_seq == seq or event_seq == seq - 1:  # Include previous event too
                evt = event.get("event", {})
                evt_type = evt.get("type")
                
                if evt_type in ("POLICY_DENIED", "STEP_END", "STEP_START"):
                    evidence_item = {
                        "type": evt_type,
                        "seq": event_seq,
                        "event_id": f"event_{event_seq}",
                        "ts": event.get("ts", ""),
                        "trace_line": idx + 1,  # Line number in trace.jsonl (1-indexed)
                    }
                    
                    # Add relevant data
                    data = evt.get("data", {})
                    if evt_type == "POLICY_DENIED":
                        policy = data.get("policy", {})
                        evidence_item["message"] = policy.get("reason", "Policy denied")
                        # Add snippet of policy data
                        try:
                            import json
                            evidence_item["snippet"] = json.dumps({
                                "type": evt_type,
                                "policy": {
                                    "rule_id": policy.get("rule_id"),
                                    "rule_name": policy.get("rule_name"),
                                    "reason": policy.get("reason"),
                                }
                            }, indent=2)
                        except:
                            pass
                    elif evt_type == "STEP_END":
                        result = data.get("result", {})
                        error = result.get("error")
                        if error:
                            evidence_item["message"] = error.get("message", "Step failed")
                            # Add snippet of error data
                            try:
                                import json
                                evidence_item["snippet"] = json.dumps({
                                    "type": evt_type,
                                    "error": {
                                        "code": error.get("code"),
                                        "message": error.get("message"),
                                    }
                                }, indent=2)
                            except:
                                pass
                    elif evt_type == "STEP_START":
                        step = evt.get("step", {})
                        # Add snippet of step data
                        try:
                            import json
                            evidence_item["snippet"] = json.dumps({
                                "type": evt_type,
                                "step": {
                                    "tool": step.get("tool"),
                                    "seq": step.get("seq"),
                                }
                            }, indent=2)
                        except:
                            pass
                    
                    evidence.append(evidence_item)
        
        return evidence


# Singleton instance
_replay_service: Optional[ReplayService] = None


def get_replay_service() -> ReplayService:
    """Get replay service singleton"""
    global _replay_service
    if _replay_service is None:
        _replay_service = ReplayService()
    return _replay_service


__all__ = ["ReplayService", "get_replay_service"]
