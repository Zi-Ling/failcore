# failcore/web/services/repos/cost_repo_trace.py
"""
Cost Repository - Trace file implementation

Provides data access abstraction for trace.jsonl files.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from failcore.utils.paths import get_failcore_root


class CostRepoTrace:
    """
    Trace file repository for cost data
    
    Parses trace.jsonl files to extract cost metrics from STEP_END events.
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
    
    def get_run_curve(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Parse cost curve from trace.jsonl
        
        Args:
            run_id: Run ID
        
        Returns:
            List of cost points (ordered by seq)
        """
        trace_path = self.find_trace_file(run_id)
        if not trace_path:
            return []
        
        points = []
        
        try:
            with open(trace_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    event = json.loads(line)
                    evt = event.get("event", {})
                    evt_type = evt.get("type")
                    
                    if evt_type == "STEP_END":
                        # Extract cost metrics
                        data = evt.get("data", {})
                        metrics = data.get("metrics", {})
                        cost_metrics = metrics.get("cost")
                        
                        if cost_metrics:
                            incremental = cost_metrics.get("incremental", {})
                            cumulative = cost_metrics.get("cumulative", {})
                            
                            result = data.get("result", {})
                            step = evt.get("step", {})
                            
                            error = result.get("error")
                            error_code = error.get("code") if error else None
                            
                            point = {
                                "seq": event.get("seq", 0),
                                "ts": event.get("ts", ""),
                                "delta_cost_usd": incremental.get("cost_usd", 0.0),
                                "cumulative_cost_usd": cumulative.get("cost_usd", 0.0),
                                "delta_tokens": incremental.get("tokens", 0),
                                "cumulative_tokens": cumulative.get("tokens", 0),
                                "delta_api_calls": incremental.get("api_calls", 0),
                                "cumulative_api_calls": cumulative.get("api_calls", 0),
                                "status": result.get("status", "OK"),
                                "tool": step.get("tool", ""),
                                "error_code": error_code,
                            }
                            points.append(point)
        except Exception:
            pass
        
        return points
    
    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run summary from trace (derived from last point)
        
        Args:
            run_id: Run ID
        
        Returns:
            Run summary dict or None if not found
        """
        points = self.get_run_curve(run_id)
        if not points:
            return None
        
        last_point = points[-1]
        return {
            "total_cost_usd": last_point.get("cumulative_cost_usd", 0.0),
            "total_tokens": last_point.get("cumulative_tokens", 0),
            "total_api_calls": last_point.get("cumulative_api_calls", 0),
            "total_steps": len(points),
        }
    
    def get_budget_for_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get budget from trace (not available in trace, returns None)
        
        Args:
            run_id: Run ID
        
        Returns:
            None (budget not stored in trace)
        """
        # Budget is not stored in trace files
        return None
    
    def is_available(self) -> bool:
        """
        Check if trace repository is available
        
        Returns:
            True (trace files are always available if failcore_root exists)
        """
        try:
            return self.failcore_root.exists()
        except Exception:
            return False


__all__ = ["CostRepoTrace"]
