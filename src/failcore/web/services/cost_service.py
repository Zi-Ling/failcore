# failcore/web/services/cost_service.py
"""
Cost Service - unified data source for cost tracking

Provides single entry point for cost data with fallback strategy:
1. SQLite (primary) - fast, structured
2. Trace (fallback) - parse trace.jsonl for STEP_END.metrics.cost

Uses repository pattern to isolate data access logic.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .repos.cost_repo_sqlite import CostRepoSqlite
from .repos.cost_repo_trace import CostRepoTrace


@dataclass
class CostPoint:
    """Single point in cost curve"""
    seq: int
    ts: str
    delta_cost_usd: float
    cum_cost_usd: float
    delta_tokens: int
    cum_tokens: int
    delta_api_calls: int
    cum_api_calls: int
    status: str  # "OK", "BLOCKED", etc.
    tool: str
    error_code: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "delta_cost_usd": self.delta_cost_usd,
            "cum_cost_usd": self.cum_cost_usd,
            "delta_tokens": self.delta_tokens,
            "cum_tokens": self.cum_tokens,
            "delta_api_calls": self.delta_api_calls,
            "cum_api_calls": self.cum_api_calls,
            "status": self.status,
            "tool": self.tool,
            "error_code": self.error_code,
        }


@dataclass
class CostBudget:
    """Budget limits applied to a run"""
    max_cost_usd: Optional[float] = None
    max_tokens: Optional[int] = None
    max_usd_per_minute: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "max_cost_usd": self.max_cost_usd,
            "max_tokens": self.max_tokens,
            "max_usd_per_minute": self.max_usd_per_minute,
        }


@dataclass
class CostEvent:
    """Cost-related event (blocked step, etc.)"""
    type: str  # "blocked", "budget_exceeded", "burn_rate_exceeded", etc.
    seq: int
    ts: str
    reason: str
    error_code: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type,
            "seq": self.seq,
            "ts": self.ts,
            "reason": self.reason,
            "error_code": self.error_code,
        }


class CostService:
    """
    Cost data service with unified data model
    
    Uses repository pattern to abstract data access:
    - CostRepoSqlite: SQLite storage (primary)
    - CostRepoTrace: Trace file parsing (fallback)
    
    Strategy:
    1. Try SQLite repository first (fast, structured)
    2. Fallback to trace repository if SQLite unavailable
    3. Normalize all sources to same data structure
    """
    
    def __init__(self, sqlite_repo: Optional[CostRepoSqlite] = None, trace_repo: Optional[CostRepoTrace] = None):
        """
        Initialize cost service
        
        Args:
            sqlite_repo: Optional SQLite repository (creates default if None)
            trace_repo: Optional trace repository (creates default if None)
        """
        self.sqlite_repo = sqlite_repo or CostRepoSqlite()
        self.trace_repo = trace_repo or CostRepoTrace()
    
    def get_run_cost(self, run_id: str) -> Dict[str, Any]:
        """
        Get cost data for a run
        
        Returns:
            {
                "points": List[CostPoint],  # Cost curve points
                "budget": CostBudget,       # Budget limits
                "events": List[CostEvent],  # Blocked events
            }
        """
        # Try SQLite repository first
        if self.sqlite_repo.is_available():
            try:
                return self._normalize_from_repo(run_id, self.sqlite_repo)
            except Exception:
                # Fallback to trace if SQLite fails
                pass
        
        # Fallback to trace repository
        return self._normalize_from_repo(run_id, self.trace_repo)
    
    def _normalize_from_repo(self, run_id: str, repo) -> Dict[str, Any]:
        """
        Normalize data from repository to unified model
        
        Args:
            run_id: Run ID
            repo: Repository instance (CostRepoSqlite or CostRepoTrace)
        
        Returns:
            Normalized cost data dict
        """
        # Get usage curve
        usage_records = repo.get_run_curve(run_id)
        
        # Normalize to CostPoint
        points = []
        for record in usage_records:
            point = CostPoint(
                seq=record.get("seq", 0),
                ts=record.get("ts", ""),
                delta_cost_usd=record.get("delta_cost_usd", 0.0) or record.get("cumulative_cost_usd", 0.0),
                cum_cost_usd=record.get("cumulative_cost_usd", 0.0),
                delta_tokens=record.get("delta_tokens", 0),
                cum_tokens=record.get("cumulative_tokens", 0),
                delta_api_calls=record.get("delta_api_calls", 0) or record.get("cumulative_api_calls", 0),
                cum_api_calls=record.get("cumulative_api_calls", 0),
                status=record.get("status", "OK"),
                tool=record.get("tool", ""),
                error_code=record.get("error_code"),
            )
            points.append(point)
        
        # Get budget
        budget_record = repo.get_budget_for_run(run_id)
        budget = CostBudget(
            max_cost_usd=budget_record.get("max_cost_usd") if budget_record else None,
            max_tokens=budget_record.get("max_tokens") if budget_record else None,
            max_usd_per_minute=budget_record.get("max_usd_per_minute") if budget_record else None,
        ) if budget_record else CostBudget()
        
        # Extract blocked events from points
        # Priority: error_code from trace > status inference from SQLite
        events = []
        for point in points:
            if point.status in ("BLOCKED", "blocked"):
                # Determine event type from error_code
                error_code = point.error_code
                event_type = "blocked"  # default
                reason = f"Step {point.seq} blocked by {point.tool}"
                
                if error_code:
                    # Map error codes to event types
                    if "BUDGET" in error_code or "ECONOMIC_BUDGET_EXCEEDED" in error_code:
                        event_type = "budget_exceeded"
                        reason = f"Step {point.seq} blocked: Budget exceeded ({error_code})"
                    elif "BURN_RATE" in error_code or "ECONOMIC_BURN_RATE_EXCEEDED" in error_code:
                        event_type = "burn_rate_exceeded"
                        reason = f"Step {point.seq} blocked: Burn rate exceeded ({error_code})"
                    elif "TOKENS" in error_code or "ECONOMIC_TOKEN_LIMIT" in error_code:
                        event_type = "token_limit_exceeded"
                        reason = f"Step {point.seq} blocked: Token limit exceeded ({error_code})"
                    else:
                        event_type = "blocked"
                        reason = f"Step {point.seq} blocked: {error_code}"
                else:
                    # Infer from status (fallback)
                    event_type = "blocked"
                    reason = f"Step {point.seq} blocked by {point.tool}"
                
                events.append(CostEvent(
                    type=event_type,
                    seq=point.seq,
                    ts=point.ts,
                    reason=reason,
                    error_code=error_code,
                ))
        
        return {
            "points": [p.to_dict() for p in points],
            "budget": budget.to_dict(),
            "events": [e.to_dict() for e in events],
        }


# Singleton instance
_cost_service: Optional[CostService] = None


def get_cost_service() -> CostService:
    """Get cost service singleton"""
    global _cost_service
    if _cost_service is None:
        _cost_service = CostService()
    return _cost_service


__all__ = ["CostService", "CostPoint", "CostBudget", "CostEvent", "get_cost_service"]
