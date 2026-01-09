# failcore/core/cost/execution.py
"""
Cost Execution - cost metrics building and storage recording

This module handles cost-related operations during step execution:
- CostRunAccumulator: Pure in-memory accumulator for run-level cost tracking
- CostRecorder: Storage writer for persisting cost data
- build_cost_metrics: Pure function for building cost metrics dict

Design principles:
- Metrics ≠ Storage: build_cost_metrics is pure, no storage dependency
- Accumulator is pure memory state, no I/O
- Recorder handles all storage writes
- commit flag: only actual execution commits to accumulator (adopts suggestion 6)
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from .models import CostUsage
from ...infra.storage.cost import CostStorage


class CostRunAccumulator:
    """
    Pure in-memory accumulator for run-level cost tracking
    
    Only accumulates costs that are actually committed (commit=True).
    Estimated costs (commit=False) are not accumulated.
    """
    
    def __init__(self):
        """Initialize accumulator with empty state"""
        self._run_cumulative: Dict[str, Dict[str, float]] = {}
        # Format: {run_id: {"cost_usd": float, "tokens": int, "api_calls": int}}
    
    def add_usage(
        self,
        run_id: str,
        usage: CostUsage,
        commit: bool = True,
    ) -> None:
        """
        Add usage to accumulator
        
        Args:
            run_id: Run ID
            usage: Cost usage to add
            commit: If True, commit to cumulative; if False, only record estimated (for pre-check)
        
        Note:
            - commit=True: Actual execution, accumulate to cumulative
            - commit=False: Estimated/pre-check, do NOT accumulate (adopts suggestion 6)
        """
        if not commit:
            # Estimated usage: don't accumulate, just return
            return
        
        # Initialize run cumulative if not exists
        if run_id not in self._run_cumulative:
            self._run_cumulative[run_id] = {
                "cost_usd": 0.0,
                "tokens": 0,
                "api_calls": 0,
            }
        
        # Accumulate actual usage
        self._run_cumulative[run_id]["cost_usd"] += float(usage.cost_usd)
        self._run_cumulative[run_id]["tokens"] += int(usage.total_tokens)
        self._run_cumulative[run_id]["api_calls"] += int(usage.api_calls)
    
    def get_cumulative(self, run_id: str) -> Dict[str, Any]:
        """
        Get cumulative cost for a run
        
        Args:
            run_id: Run ID
        
        Returns:
            Dict with cost_usd, tokens, api_calls
        """
        return self._run_cumulative.get(run_id, {
            "cost_usd": 0.0,
            "tokens": 0,
            "api_calls": 0,
        })
    
    def reset(self, run_id: str) -> None:
        """
        Reset cumulative cost for a run
        
        Args:
            run_id: Run ID to reset
        """
        if run_id in self._run_cumulative:
            del self._run_cumulative[run_id]


class CostRecorder:
    """
    Storage writer for persisting cost data
    
    Handles all writes to CostStorage, including:
    - Step-level usage records
    - Run-level summary updates
    """
    
    def __init__(self, storage: Optional[CostStorage]):
        """
        Initialize recorder
        
        Args:
            storage: CostStorage instance (None if cost tracking disabled)
        """
        self.storage = storage
    
    def record_step(
        self,
        run_id: str,
        step_id: str,
        seq: int,
        tool: str,
        usage: Optional[CostUsage],
        metrics: Optional[Dict[str, Any]],
        status: str,
        started_at: str,
        duration_ms: int,
        error_code: Optional[str] = None,
        commit: bool = True,
    ) -> None:
        """
        Record step-level cost usage to storage
        
        Args:
            run_id: Run ID
            step_id: Step ID
            seq: Sequence number
            tool: Tool name
            usage: CostUsage object (None if no usage)
            metrics: Cost metrics dict (from build_cost_metrics)
            status: Step status ("OK", "BLOCKED", "FAIL", etc.)
            started_at: Step start timestamp
            duration_ms: Step duration in milliseconds
            error_code: Error code if failed/blocked
            commit: Whether this usage was committed to accumulator
        
        Note:
            - Even if commit=False (estimated/blocked), we still record to storage
              for audit trail, but with estimated=True flag
        """
        if not self.storage or not metrics:
            return
        
        try:
            incremental = metrics["cost"]["incremental"]
            cumulative = metrics["cost"]["cumulative"]
            
            self.storage.insert_usage(
                run_id=run_id,
                step_id=step_id,
                seq=seq,
                tool=tool,
                delta_cost_usd=incremental["cost_usd"],
                delta_tokens=incremental["tokens"],
                cumulative_cost_usd=cumulative["cost_usd"],
                cumulative_tokens=cumulative["tokens"],
                cumulative_api_calls=cumulative["api_calls"],
                status=status,
                ts=started_at,
                delta_input_tokens=incremental.get("input_tokens", 0),  # Extract from incremental if available
                delta_output_tokens=incremental.get("output_tokens", 0),  # Extract from incremental if available
                delta_api_calls=incremental["api_calls"],
                error_code=error_code,
                estimated=incremental["estimated"],
                model=incremental.get("pricing_ref"),
                provider=None,  # Not in incremental
                duration_ms=duration_ms,
            )
        except Exception as e:
            # Don't fail execution if cost storage fails
            import sys
            print(f"Warning: Failed to record cost to SQLite: {e}", file=sys.stderr)
    
    def record_run_summary(
        self,
        run_id: str,
        created_at: str,
        cumulative: Dict[str, Any],
        seq: int,
        status: str,
        blocked_step_id: Optional[str] = None,
        blocked_reason: Optional[str] = None,
        blocked_error_code: Optional[str] = None,
    ) -> None:
        """
        Update run-level summary in storage
        
        Args:
            run_id: Run ID
            created_at: Run creation timestamp
            cumulative: Cumulative cost dict (from metrics)
            seq: Last step sequence number
            status: Run status ("running", "blocked", "error", "completed")
            blocked_step_id: Step ID that caused block (if blocked)
            blocked_reason: Reason for block (if blocked)
            blocked_error_code: Error code for block (if blocked)
        """
        if not self.storage:
            return
        
        try:
            self.storage.upsert_run(
                run_id=run_id,
                created_at=created_at,
                total_cost_usd=cumulative["cost_usd"],
                total_tokens=cumulative["tokens"],
                total_api_calls=cumulative["api_calls"],
                total_steps=seq,
                last_step_seq=seq,
                status=status,
                blocked_step_id=blocked_step_id,
                blocked_reason=blocked_reason,
                blocked_error_code=blocked_error_code,
            )
        except Exception as e:
            # Don't fail execution if cost storage fails
            import sys
            print(f"Warning: Failed to update run summary in SQLite: {e}", file=sys.stderr)


def build_cost_metrics(
    run_id: str,
    usage: Optional[CostUsage],
    accumulator: CostRunAccumulator,
    commit: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Build cost metrics dict for STEP_END event
    
    Pure function: no storage dependency, no side effects.
    Only reads from accumulator, does not write.
    
    Args:
        run_id: Run ID
        usage: CostUsage object (None if cost tracking disabled)
        accumulator: CostRunAccumulator instance
        commit: Whether to commit usage to accumulator (True for actual execution)
    
    Returns:
        Metrics dict with incremental and cumulative, or None if no usage
        
    Design:
        - Incremental: cost for this step only
        - Cumulative: total cost for run so far (from accumulator)
        - commit=True: actual execution, accumulate
        - commit=False: estimated/pre-check, don't accumulate (adopts suggestion 6)
    """
    if not usage:
        return None
    
    # Commit usage to accumulator if requested
    if commit:
        accumulator.add_usage(run_id, usage, commit=True)
    
    # Incremental (this step only)
    incremental = {
        "cost_usd": float(usage.cost_usd),
        "tokens": int(usage.total_tokens),
        "api_calls": int(usage.api_calls),
        "estimated": bool(usage.estimated),
        "source": usage.source,  # Add source for traceability
    }
    
    # Include input/output tokens if available
    if usage.input_tokens > 0:
        incremental["input_tokens"] = int(usage.input_tokens)
    if usage.output_tokens > 0:
        incremental["output_tokens"] = int(usage.output_tokens)
    
    # Optional: pricing_ref (format: provider:model)
    if usage.model and usage.provider:
        incremental["pricing_ref"] = f"{usage.provider}:{usage.model}"
    
    # Optional: raw_usage for debugging (if available)
    if usage.raw_usage:
        incremental["raw_usage"] = usage.raw_usage
    
    # Cumulative (entire run so far)
    # If commit=False, get current cumulative (before this step)
    # If commit=True, get updated cumulative (after accumulator.add_usage)
    cumulative = accumulator.get_cumulative(run_id)
    
    return {
        "cost": {
            "incremental": incremental,
            "cumulative": {
                "cost_usd": float(cumulative["cost_usd"]),
                "tokens": int(cumulative["tokens"]),
                "api_calls": int(cumulative["api_calls"]),
            },
        }
    }


__all__ = [
    "CostRunAccumulator",
    "CostRecorder",
    "build_cost_metrics",
]
