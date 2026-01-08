# failcore/web/services/events_service.py
"""
Events Service - real-time event streaming from trace files

Extracts BLOCKED events from trace.jsonl and streams them via SSE.
"""

from typing import AsyncIterator, Dict, Any, Optional, List
from datetime import datetime
import json
import asyncio

from .repos.trace_repo import TraceRepo


class EventsService:
    """
    Events service for real-time event streaming
    
    Extracts events from trace files and provides SSE streaming.
    Event format matches CostEvent from cost_service.py:
    {
        "type": "blocked" | "budget_exceeded" | "burn_rate_exceeded",
        "seq": int,
        "ts": str (ISO timestamp),
        "reason": str,
        "error_code": Optional[str],
        "run_id": str
    }
    """
    
    def __init__(self):
        """Initialize events service"""
        self.trace_repo = TraceRepo()
        self._active_streams: Dict[str, asyncio.Queue] = {}
    
    def _extract_events_from_trace(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Extract BLOCKED events from trace file.
        
        Args:
            run_id: Run ID
        
        Returns:
            List of event dictionaries
        """
        events = []
        trace_events = self.trace_repo.load_trace_events(run_id)
        
        for event in trace_events:
            evt = event.get("event", {})
            evt_type = evt.get("type")
            seq = event.get("seq", 0)
            ts = event.get("ts", "")
            
            # Check for BLOCKED status in STEP_END
            if evt_type == "STEP_END":
                data = evt.get("data", {})
                result = data.get("result", {})
                status = result.get("status", "")
                error = result.get("error", {})
                
                if status == "BLOCKED" or error:
                    error_code = error.get("code", "")
                    error_message = error.get("message", "")
                    
                    # Determine event type
                    event_type = "blocked"
                    reason = f"Step {seq} blocked"
                    
                    if error_code:
                        if "BUDGET" in error_code:
                            event_type = "budget_exceeded"
                            reason = f"Step {seq} blocked: Budget exceeded ({error_code})"
                        elif "BURN_RATE" in error_code:
                            event_type = "burn_rate_exceeded"
                            reason = f"Step {seq} blocked: Burn rate exceeded ({error_code})"
                        else:
                            reason = f"Step {seq} blocked: {error_code}"
                    
                    events.append({
                        "type": event_type,
                        "seq": seq,
                        "ts": ts,
                        "reason": reason,
                        "error_code": error_code,
                        "run_id": run_id,
                    })
        
        return events
    
    async def stream_run_events(
        self,
        run_id: str,
        last_event_seq: Optional[int] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream events for a run (SSE)
        
        Args:
            run_id: Run ID
            last_event_seq: Last event sequence number (for resume)
        
        Yields:
            Event dictionaries in SSE format
        """
        # Extract events from trace
        all_events = self._extract_events_from_trace(run_id)
        
        # Filter by last_event_seq if provided
        if last_event_seq is not None:
            all_events = [e for e in all_events if e.get("seq", 0) > last_event_seq]
        
        # Yield events
        for event in all_events:
            yield event
        
        # For real-time streaming, we would watch the trace file for new events
        # For now, we just return existing events from the trace
    
    def get_run_events(
        self,
        run_id: str,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Dict[str, Any]]:
        """
        Get events for a run (non-streaming)
        
        Args:
            run_id: Run ID
            event_type: Optional event type filter
            limit: Optional limit on number of events
        
        Returns:
            List of event dictionaries
        """
        events = self._extract_events_from_trace(run_id)
        
        # Filter by event_type if provided
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        
        # Apply limit if provided
        if limit is not None:
            events = events[:limit]
        
        return events
    
    def get_side_effect_findings(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get side-effect boundary crossings for a run
        
        Args:
            run_id: Run ID
        
        Returns:
            List of side-effect crossing findings
        """
        findings = []
        trace_events = self.trace_repo.load_trace_events(run_id)
        
        for event in trace_events:
            evt = event.get("event", {})
            evt_type = evt.get("type")
            seq = event.get("seq", 0)
            ts = event.get("ts", "")
            
            if evt_type == "STEP_END":
                data = evt.get("data", {})
                result = data.get("result", {})
                error = result.get("error")
                if error and error.get("type") == "SIDE_EFFECT_BOUNDARY_CROSSED":
                    details = error.get("details", {})
                    findings.append({
                        "crossing_type": details.get("crossing_type"),
                        "observed_category": details.get("observed_category"),
                        "target": details.get("target"),
                        "tool": details.get("tool"),
                        "step_id": details.get("step_id"),
                        "step_seq": details.get("step_seq", seq),
                        "ts": ts,
                        "allowed_categories": details.get("allowed_categories", []),
                    })
        
        return findings


# Singleton instance
_events_service: Optional[EventsService] = None


def get_events_service() -> EventsService:
    """Get events service singleton"""
    global _events_service
    if _events_service is None:
        _events_service = EventsService()
    return _events_service


__all__ = ["EventsService", "get_events_service"]
