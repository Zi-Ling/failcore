# failcore/web/services/repos/trace_repo.py
"""
Trace Repository - trace file access abstraction

Provides data access abstraction for trace.jsonl files.
Separates trace file location/parsing from business logic.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from failcore.utils.paths import get_failcore_root


class TraceRepo:
    """
    Trace file repository
    
    Handles trace file location and basic parsing.
    Business logic should use ReplayService which uses this repo.
    """
    
    def __init__(self):
        """Initialize trace repository"""
        self.failcore_root = get_failcore_root()
    
    def find_trace_file(self, run_id: str) -> Optional[Path]:
        """
        Find trace file for a run_id
        
        Args:
            run_id: Run ID (format: {date}_{run_name} or full run_id)
        
        Returns:
            Path to trace.jsonl or None if not found
        """
        # Try parsing run_id (format: {date}_{run_name})
        if "_" in run_id:
            parts = run_id.split("_", 1)
            if len(parts) == 2:
                date, run_name = parts
                trace_path = self.failcore_root / "runs" / date / run_name / "trace.jsonl"
                if trace_path.exists():
                    return trace_path
        
        # If not found, search in runs directory
        runs_dir = self.failcore_root / "runs"
        if not runs_dir.exists():
            return None
        
        for date_dir in runs_dir.iterdir():
            if not date_dir.is_dir():
                continue
            for run_dir in date_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                potential_trace = run_dir / "trace.jsonl"
                if potential_trace.exists():
                    # Read first event to check run_id
                    try:
                        with open(potential_trace, 'r', encoding='utf-8') as f:
                            first_line = f.readline().strip()
                            if first_line:
                                event = json.loads(first_line)
                                event_run_id = event.get("run", {}).get("run_id", "")
                                # Match full run_id or {date}_{run_name} format
                                if event_run_id == run_id or f"{date_dir.name}_{run_dir.name}" == run_id:
                                    return potential_trace
                    except Exception:
                        continue
        
        return None
    
    def load_trace_events(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Load all events from trace file
        
        Args:
            run_id: Run ID
        
        Returns:
            List of trace events (as dicts)
        """
        trace_path = self.find_trace_file(run_id)
        if not trace_path:
            return []
        
        events = []
        try:
            with open(trace_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    events.append(json.loads(line))
        except Exception:
            pass
        
        return events
    
    def is_available(self) -> bool:
        """
        Check if trace repository is available
        
        Returns:
            True if failcore_root exists
        """
        try:
            return self.failcore_root.exists()
        except Exception:
            return False


__all__ = ["TraceRepo"]
