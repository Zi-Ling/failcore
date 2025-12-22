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
        """Index event for quick lookup"""
        evt = event.get("event", {})
        evt_type = evt.get("type")
        step = evt.get("step", {})
        
        if not step:
            return
        
        run_id = event.get("run", {}).get("run_id", "unknown")
        step_id = step.get("id")
        
        if not step_id:
            return
        
        key = (run_id, step_id)
        
        # Build step info
        if key not in self.steps_by_id:
            self.steps_by_id[key] = {
                "run_id": run_id,
                "step_id": step_id,
                "tool": step.get("tool"),
                "attempt": step.get("attempt", 1),
                "start_event": None,
                "end_event": None,
                "other_events": [],
            }
        
        step_info = self.steps_by_id[key]
        
        # Store events
        if evt_type == "STEP_START":
            step_info["start_event"] = event
            
            # Index by fingerprint
            fingerprint = step.get("fingerprint", {})
            fp_id = fingerprint.get("id")
            if fp_id:
                if fp_id not in self.events_by_fingerprint:
                    self.events_by_fingerprint[fp_id] = []
                self.events_by_fingerprint[fp_id].append(event)
        
        elif evt_type == "STEP_END":
            step_info["end_event"] = event
        
        else:
            step_info["other_events"].append(event)
    
    def get_step(self, run_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Get step info by run_id and step_id"""
        return self.steps_by_id.get((run_id, step_id))
    
    def get_by_fingerprint(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """Get step by fingerprint ID"""
        events = self.events_by_fingerprint.get(fingerprint_id)
        if not events:
            return None
        
        # Return the first STEP_START event
        for event in events:
            evt = event.get("event", {})
            if evt.get("type") == "STEP_START":
                run_id = event.get("run", {}).get("run_id")
                step_id = evt.get("step", {}).get("id")
                return self.get_step(run_id, step_id)
        
        return None
    
    def get_all_steps(self) -> List[Dict[str, Any]]:
        """Get all steps"""
        return list(self.steps_by_id.values())
