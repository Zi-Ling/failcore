# failcore/core/replay/loader.py
"""
Trace loader for replay
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path


class TraceLoader:
    """
    Load and index trace events for replay
    
    Indexes by:
    - run_id
    - step_id
    - fingerprint_id
    """
    
    def __init__(self, trace_path: str):
        self.trace_path = trace_path
        self.events: List[Dict[str, Any]] = []
        self.steps_by_id: Dict[tuple, Dict[str, Any]] = {}  # (run_id, step_id) -> step info
        self.events_by_fingerprint: Dict[str, List[Dict[str, Any]]] = {}  # fingerprint_id -> events
        
        self._load()
    
    def _load(self):
        """Load trace file and build indexes"""
        if not Path(self.trace_path).exists():
            raise FileNotFoundError(f"Trace file not found: {self.trace_path}")
        
        with open(self.trace_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event = json.loads(line)
                    self.events.append(event)
                    self._index_event(event)
                except json.JSONDecodeError:
                    continue
    
    def _index_event(self, event: Dict[str, Any]):
        """
        Index event for quick lookup (v0.1.3 unified model)
        
        Behavior:
        - Indexes ATTEMPT and RESULT events by step_id
        - Collects EGRESS_EVENT with step_id as evidence
        - All events must contain step_id for association
        """
        evt = event.get("event", {})
        evt_type = evt.get("type")
        
        # Extract step_id from either event.step.id or event.data.step_id (EGRESS_EVENT)
        step = evt.get("step", {})
        step_id = step.get("id")
        
        # For EGRESS_EVENT, step_id might be in data
        if not step_id and evt_type == "EGRESS_EVENT":
            data = evt.get("data", {})
            step_id = data.get("step_id")
        
        if not step_id:
            return
        
        run_id = event.get("run", {}).get("run_id", "unknown")
        key = (run_id, step_id)
        
        # Build step info on first encounter
        if key not in self.steps_by_id:
            self.steps_by_id[key] = {
                "run_id": run_id,
                "step_id": step_id,
                "tool": step.get("tool"),
                "attempt": step.get("attempt", 1),
                "attempt_event": None,  # Renamed from start_event
                "result_event": None,   # Renamed from end_event
                "egress_events": [],    # Renamed from other_events
            }
        
        step_info = self.steps_by_id[key]
        
        # Index by event type (v0.1.3 unified model)
        if evt_type == "ATTEMPT":
            step_info["attempt_event"] = event
            step_info["tool"] = step.get("tool", step_info["tool"])
            
            # Index by fingerprint
            fingerprint = step.get("fingerprint", {})
            fp_id = fingerprint.get("id")
            if fp_id:
                if fp_id not in self.events_by_fingerprint:
                    self.events_by_fingerprint[fp_id] = []
                self.events_by_fingerprint[fp_id].append(event)
        
        elif evt_type == "RESULT":
            step_info["result_event"] = event
        
        elif evt_type == "EGRESS_EVENT":
            # Collect EGRESS_EVENT as evidence
            step_info["egress_events"].append(event)
        
        else:
            # Other events (POLICY_DENIED, VALIDATION_FAILED, etc.) also as evidence
            step_info["egress_events"].append(event)
    
    def get_step(self, run_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Get step info by run_id and step_id"""
        return self.steps_by_id.get((run_id, step_id))
    
    def get_by_fingerprint(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """Get step by fingerprint ID"""
        events = self.events_by_fingerprint.get(fingerprint_id)
        if not events:
            return None
        
        # Return the first ATTEMPT event
        for event in events:
            evt = event.get("event", {})
            if evt.get("type") == "ATTEMPT":
                run_id = event.get("run", {}).get("run_id")
                step_id = evt.get("step", {}).get("id")
                return self.get_step(run_id, step_id)
        
        return None
    
    def get_all_steps(self) -> List[Dict[str, Any]]:
        """
        Get all steps (sorted by sequence)
        
        Returns frames built from ATTEMPT + RESULT + EGRESS_EVENTs
        """
        steps = []
        for step_info in self.steps_by_id.values():
            # Only include steps that have an ATTEMPT event
            if step_info.get("attempt_event"):
                steps.append(step_info)
        
        # Sort by attempt event sequence
        steps.sort(key=lambda s: s.get("attempt_event", {}).get("seq", 0))
        return steps
