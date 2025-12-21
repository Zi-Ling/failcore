# failcore/infra/storage/ingest.py
"""
Trace ingestor - converts trace.jsonl to database
"""

import json
from typing import Dict, Any, Optional
from collections import defaultdict
from .sqlite_store import SQLiteStore


class TraceIngestor:
    """
    Ingest trace.jsonl into database
    
    Aggregation rules:
    - STEP_START -> step.start_ts, fingerprint_id
    - STEP_END -> step.end_ts, status, phase, duration_ms
    - POLICY_DENIED -> step.has_policy_denied = 1
    - OUTPUT_NORMALIZED -> step.has_output_normalized = 1, warnings
    """
    
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.step_cache: Dict[tuple, Dict[str, Any]] = {}  # (run_id, step_id, attempt) -> step_data
    
    def ingest_file(self, trace_path: str, skip_if_exists: bool = False) -> Dict[str, int]:
        """
        Ingest trace file into database
        
        Args:
            trace_path: Path to trace.jsonl
            skip_if_exists: If True, skip if run_id already exists
        
        Returns:
            Statistics: {"events": count, "steps": count, "errors": count, "skipped": bool}
        """
        stats = {"events": 0, "steps": 0, "errors": 0, "incomplete": 0, "skipped": False}
        
        run_metadata = {
            "run_id": None,
            "created_at": None,
            "workspace": None,
            "sandbox_root": None,
            "trace_path": trace_path,
            "first_event_ts": None,
            "last_event_ts": None,
            "total_events": 0,
            "total_steps": 0,
        }
        
        # Read first event to get run_id
        with open(trace_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                        run = event.get("run", {})
                        run_metadata["run_id"] = run.get("run_id")
                        break
                    except:
                        pass
        
        # Check if run already exists
        if skip_if_exists and run_metadata["run_id"]:
            cursor = self.store.conn.cursor()
            cursor.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_metadata["run_id"],))
            if cursor.fetchone():
                stats["skipped"] = True
                return stats
        
        # Read and process events
        with open(trace_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event = json.loads(line)
                    
                    # Extract run metadata from first event
                    if not run_metadata["created_at"]:
                        run = event.get("run", {})
                        run_metadata["created_at"] = run.get("created_at")
                        run_metadata["workspace"] = run.get("workspace")
                        run_metadata["sandbox_root"] = run.get("sandbox_root")
                        run_metadata["first_event_ts"] = event.get("ts")
                    
                    # Update last event timestamp
                    run_metadata["last_event_ts"] = event.get("ts")
                    run_metadata["total_events"] += 1
                    
                    # Insert raw event
                    self.store.insert_event(event)
                    stats["events"] += 1
                    
                    # Process for step aggregation
                    self._process_event(event)
                    
                except json.JSONDecodeError:
                    stats["errors"] += 1
                except Exception as e:
                    stats["errors"] += 1
        
        # Flush step cache to database
        for step_data in self.step_cache.values():
            # Check if step is incomplete (missing START or END)
            if not step_data.get("start_ts") or not step_data.get("end_ts"):
                step_data["status"] = "INCOMPLETE"
                stats["incomplete"] += 1
            
            self.store.upsert_step(step_data)
            stats["steps"] += 1
        
        run_metadata["total_steps"] = stats["steps"]
        
        # Upsert run metadata
        if run_metadata["run_id"]:
            self.store.upsert_run(run_metadata["run_id"], run_metadata)
        
        self.store.commit()
        
        return stats
    
    def _process_event(self, event: Dict[str, Any]):
        """Process event for step aggregation"""
        evt = event.get("event", {})
        evt_type = evt.get("type")
        
        if not evt_type:
            return
        
        # Only process step-related events
        if evt_type not in ("STEP_START", "STEP_END", "POLICY_DENIED", "OUTPUT_NORMALIZED", "VALIDATION_FAILED"):
            return
        
        step = evt.get("step", {})
        step_id = step.get("id")
        if not step_id:
            return
        
        run_id = event.get("run", {}).get("run_id", "unknown")
        tool = step.get("tool", "")
        attempt = step.get("attempt", 1)
        
        key = (run_id, step_id, attempt)
        
        # Get or create step entry
        if key not in self.step_cache:
            self.step_cache[key] = {
                "run_id": run_id,
                "step_id": step_id,
                "tool": tool,
                "attempt": attempt,
                "warnings": None,
                "has_policy_denied": 0,
                "has_output_normalized": 0,
            }
        
        step_data = self.step_cache[key]
        
        # Process by event type
        if evt_type == "STEP_START":
            step_data["start_seq"] = event.get("seq")
            step_data["start_ts"] = event.get("ts")
            
            # Extract fingerprint
            fingerprint = step.get("fingerprint", {})
            if fingerprint:
                step_data["fingerprint_id"] = fingerprint.get("id")
        
        elif evt_type == "STEP_END":
            step_data["end_seq"] = event.get("seq")
            step_data["end_ts"] = event.get("ts")
            
            data = evt.get("data", {})
            result = data.get("result", {})
            
            step_data["status"] = result.get("status")
            step_data["phase"] = result.get("phase")
            step_data["duration_ms"] = result.get("duration_ms")
            
            # Extract error
            error = result.get("error")
            if error:
                step_data["error_code"] = error.get("code")
                step_data["error_message"] = error.get("message")
            
            # Extract warnings
            warnings = result.get("warnings")
            if warnings:
                step_data["warnings"] = json.dumps(warnings)
        
        elif evt_type == "POLICY_DENIED":
            step_data["has_policy_denied"] = 1
            # Mark as blocked if not already set
            if not step_data.get("status"):
                step_data["status"] = "BLOCKED"
                step_data["phase"] = "policy"
        
        elif evt_type == "OUTPUT_NORMALIZED":
            step_data["has_output_normalized"] = 1
            data = evt.get("data", {})
            normalize = data.get("normalize", {})
            if normalize.get("decision") == "mismatch":
                # Add to warnings
                warnings = []
                if step_data.get("warnings"):
                    warnings = json.loads(step_data["warnings"])
                warnings.append("OUTPUT_KIND_MISMATCH")
                step_data["warnings"] = json.dumps(warnings)
        
        elif evt_type == "VALIDATION_FAILED":
            # Add validation failure to warnings
            warnings = []
            if step_data.get("warnings"):
                warnings = json.loads(step_data["warnings"])
            warnings.append("VALIDATION_FAILED")
            step_data["warnings"] = json.dumps(warnings)
