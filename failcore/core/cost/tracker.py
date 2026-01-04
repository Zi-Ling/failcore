"""
Cost Guardrails - Tracker

Track actual cost usage and write to trace/receipt
"""

import json
from pathlib import Path
from typing import List, Optional
from .models import CostUsage, Budget


class CostTracker:
    """
    Track cost usage across runs
    
    Supports:
    - Per-run cost tracking
    - Aggregated cost reporting
    - Budget monitoring
    """
    
    def __init__(self, storage_path: str = "./.failcore/cost"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def record(self, usage: CostUsage) -> None:
        """Record cost usage to disk"""
        # Organize by run_id
        run_dir = self.storage_path / usage.run_id
        run_dir.mkdir(exist_ok=True)
        
        # Append to usage log
        usage_file = run_dir / "usage.jsonl"
        with open(usage_file, 'a') as f:
            f.write(json.dumps(usage.to_dict()) + '\n')
    
    def get_run_usage(self, run_id: str) -> List[CostUsage]:
        """Get all usage records for a run"""
        usage_file = self.storage_path / run_id / "usage.jsonl"
        
        if not usage_file.exists():
            return []
        
        usages = []
        with open(usage_file) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    usage = CostUsage(
                        run_id=data["run_id"],
                        step_id=data["step_id"],
                        tool_name=data["tool_name"],
                        input_tokens=data.get("input_tokens", 0),
                        output_tokens=data.get("output_tokens", 0),
                        total_tokens=data.get("total_tokens", 0),
                        cost_usd=data.get("cost_usd", 0.0),
                        estimated=data.get("estimated", True),
                        api_calls=data.get("api_calls", 1),
                        model=data.get("model"),
                        provider=data.get("provider"),
                        timestamp=data.get("timestamp", ""),
                    )
                    usages.append(usage)
        
        return usages
    
    def get_run_summary(self, run_id: str) -> dict:
        """Get cost summary for a run"""
        usages = self.get_run_usage(run_id)
        
        if not usages:
            return {
                "run_id": run_id,
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "total_api_calls": 0,
                "tool_count": 0,
            }
        
        return {
            "run_id": run_id,
            "total_cost_usd": sum(u.cost_usd for u in usages),
            "total_tokens": sum(u.total_tokens for u in usages),
            "total_api_calls": sum(u.api_calls for u in usages),
            "tool_count": len(usages),
            "tools": list(set(u.tool_name for u in usages)),
        }
    
    def check_budget(self, run_id: str, budget: Budget) -> tuple[bool, Optional[str]]:
        """
        Check if run is within budget
        
        Returns:
            (within_budget, warning_message)
        """
        usages = self.get_run_usage(run_id)
        
        # Calculate current usage
        total_cost = sum(u.cost_usd for u in usages)
        total_tokens = sum(u.total_tokens for u in usages)
        total_api_calls = sum(u.api_calls for u in usages)
        
        # Check against budget
        warnings = []
        
        if budget.max_cost_usd is not None:
            if total_cost >= budget.max_cost_usd:
                return (False, f"Budget exceeded: ${total_cost:.4f} / ${budget.max_cost_usd:.4f}")
            elif total_cost >= budget.max_cost_usd * 0.8:
                warnings.append(f"80% budget used: ${total_cost:.4f} / ${budget.max_cost_usd:.4f}")
        
        if budget.max_tokens is not None:
            if total_tokens >= budget.max_tokens:
                return (False, f"Token budget exceeded: {total_tokens} / {budget.max_tokens}")
            elif total_tokens >= budget.max_tokens * 0.8:
                warnings.append(f"80% tokens used: {total_tokens} / {budget.max_tokens}")
        
        if budget.max_api_calls is not None:
            if total_api_calls >= budget.max_api_calls:
                return (False, f"API call budget exceeded: {total_api_calls} / {budget.max_api_calls}")
        
        if warnings:
            return (True, "; ".join(warnings))
        
        return (True, None)


__all__ = ["CostTracker"]
