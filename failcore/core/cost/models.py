"""
Cost Guardrails - Models (Optimized)

Economic safety: token/API cost tracking and budget enforcement

Key improvements:
- Strong enums (scope/unit)
- Clear ownership/targeting (run_id/user_id/org_id)
- Safer types (datetime, bool/int serialization)
- Better identity (optional id)
- Cleaner dict conversion + timestamps
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class CostUnit(str, Enum):
    """Cost unit types"""
    USD = "usd"                 # US Dollars
    TOKEN = "token"             # Token count
    API_CALL = "api_call"       # API call count
    COMPUTE_UNIT = "compute_unit"  # Abstract compute units


class BudgetScope(str, Enum):
    """Budget scope granularity"""
    RUN = "run"
    DAY = "day"
    MONTH = "month"
    USER = "user"
    ORG = "org"


@dataclass(frozen=True)
class CostUsage:
    """
    Cost usage record for a single operation (usually per-step).

    Note:
      - Prefer one CostUsage per step to keep storage small and curve readable.
      - Use `estimated=False` when provider returns actual billed usage.
    """
    # Identity / targeting
    run_id: str
    step_id: str
    tool_name: str

    # Optional richer identity
    model: Optional[str] = None        # e.g., "gpt-4o", "claude-3-sonnet"
    provider: Optional[str] = None     # e.g., "openai", "anthropic"

    # Usage breakdown
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Financial cost (USD)
    cost_usd: float = 0.0
    estimated: bool = True

    # API usage
    api_calls: int = 1

    # Timestamp (prefer datetime in core; serialize at edges)
    ts: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        if self.input_tokens < 0 or self.output_tokens < 0 or self.total_tokens < 0:
            raise ValueError("token counts must be non-negative")
        if self.api_calls < 0:
            raise ValueError("api_calls must be non-negative")
        if self.cost_usd < 0:
            raise ValueError("cost_usd must be non-negative")

        # Auto-derive total_tokens if not provided
        if self.total_tokens == 0 and (self.input_tokens or self.output_tokens):
            object.__setattr__(self, "total_tokens", self.input_tokens + self.output_tokens)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage/trace emission (JSON-serializable)."""
        return {
            "run_id": self.run_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": int(self.input_tokens),
            "output_tokens": int(self.output_tokens),
            "total_tokens": int(self.total_tokens),
            "cost_usd": float(self.cost_usd),
            "estimated": bool(self.estimated),
            "api_calls": int(self.api_calls),
            "timestamp": iso_utc(self.ts),
        }


@dataclass
class Budget:
    """
    Budget constraints for cost control.

    Supports hierarchical budgets:
      - per-run (scope=RUN, run_id set)
      - per-day/month (scope=DAY/MONTH, user_id/org_id set)
      - per-user/org (scope=USER/ORG)

    Design:
      - `max_*` are constraints
      - `used_*` are counters (optional to persist; can be derived from usage table)
    """
    # Identity
    budget_id: str = "default"

    # Scope + targeting (who/what this budget applies to)
    scope: BudgetScope = BudgetScope.RUN
    run_id: Optional[str] = None
    user_id: Optional[str] = None
    org_id: Optional[str] = None

    # Budget limits (constraints)
    max_cost_usd: Optional[float] = None
    max_tokens: Optional[int] = None
    max_api_calls: Optional[int] = None

    # Current usage (counters)
    used_cost_usd: float = 0.0
    used_tokens: int = 0
    used_api_calls: int = 0

    # Metadata
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        # Basic sanity checks
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be >= 0 or None")
        if self.max_tokens is not None and self.max_tokens < 0:
            raise ValueError("max_tokens must be >= 0 or None")
        if self.max_api_calls is not None and self.max_api_calls < 0:
            raise ValueError("max_api_calls must be >= 0 or None")

        if self.used_cost_usd < 0 or self.used_tokens < 0 or self.used_api_calls < 0:
            raise ValueError("used_* counters must be non-negative")

        # Target validation by scope
        if self.scope == BudgetScope.RUN and not self.run_id:
            raise ValueError("scope=RUN requires run_id")
        if self.scope in (BudgetScope.USER, BudgetScope.DAY, BudgetScope.MONTH) and not self.user_id:
            raise ValueError(f"scope={self.scope.value} requires user_id")
        if self.scope == BudgetScope.ORG and not self.org_id:
            raise ValueError("scope=ORG requires org_id")

    def touch(self) -> None:
        self.updated_at = utc_now()

    def remaining_cost_usd(self) -> Optional[float]:
        if self.max_cost_usd is None:
            return None
        return max(0.0, self.max_cost_usd - self.used_cost_usd)

    def remaining_tokens(self) -> Optional[int]:
        if self.max_tokens is None:
            return None
        return max(0, self.max_tokens - self.used_tokens)

    def remaining_api_calls(self) -> Optional[int]:
        if self.max_api_calls is None:
            return None
        return max(0, self.max_api_calls - self.used_api_calls)

    def would_exceed(self, usage: CostUsage) -> Tuple[bool, str]:
        """
        Check if adding usage would exceed budget.

        Returns:
            (would_exceed, reason)
        """
        # USD
        if self.max_cost_usd is not None:
            if self.used_cost_usd + usage.cost_usd > self.max_cost_usd:
                remaining = self.remaining_cost_usd()
                rem_str = "0.0000" if remaining is None else f"{remaining:.4f}"
                return True, (
                    f"Would exceed USD budget: ${usage.cost_usd:.4f} needed, ${rem_str} remaining"
                )

        # Tokens
        if self.max_tokens is not None:
            if self.used_tokens + usage.total_tokens > self.max_tokens:
                remaining = self.remaining_tokens()
                rem_str = "0" if remaining is None else str(remaining)
                return True, (
                    f"Would exceed token budget: {usage.total_tokens} needed, {rem_str} remaining"
                )

        # API calls
        if self.max_api_calls is not None:
            if self.used_api_calls + usage.api_calls > self.max_api_calls:
                remaining = self.remaining_api_calls()
                rem_str = "0" if remaining is None else str(remaining)
                return True, (
                    f"Would exceed API call budget: {usage.api_calls} needed, {rem_str} remaining"
                )

        return False, ""

    def add_usage(self, usage: CostUsage) -> None:
        """Add usage to budget counters."""
        self.used_cost_usd += float(usage.cost_usd)
        self.used_tokens += int(usage.total_tokens)
        self.used_api_calls += int(usage.api_calls)
        self.touch()

    def usage_percentage(self) -> float:
        """
        Overall usage percentage (0.0 - 1.0).

        We return the max ratio across configured constraints,
        representing the most constrained dimension.
        """
        ratios = []

        if self.max_cost_usd is not None and self.max_cost_usd > 0:
            ratios.append(self.used_cost_usd / self.max_cost_usd)

        if self.max_tokens is not None and self.max_tokens > 0:
            ratios.append(self.used_tokens / self.max_tokens)

        if self.max_api_calls is not None and self.max_api_calls > 0:
            ratios.append(self.used_api_calls / self.max_api_calls)

        return max(ratios) if ratios else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage (JSON-serializable)."""
        return {
            "budget_id": self.budget_id,
            "scope": self.scope.value,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "max_cost_usd": self.max_cost_usd,
            "max_tokens": self.max_tokens,
            "max_api_calls": self.max_api_calls,
            "used_cost_usd": float(self.used_cost_usd),
            "used_tokens": int(self.used_tokens),
            "used_api_calls": int(self.used_api_calls),
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }


__all__ = [
    "CostUnit",
    "BudgetScope",
    "CostUsage",
    "Budget",
]
