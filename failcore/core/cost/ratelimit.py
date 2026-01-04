"""
Burn Rate Limiting

Control spending velocity to prevent budget exhaustion
Adds time dimension to cost control
"""

from typing import Optional, Deque
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from threading import Lock

from .models import CostUsage
from ..errors import FailCoreError, codes


@dataclass
class BurnRateConfig:
    """
    Burn rate configuration
    
    Controls spending velocity over time windows
    """
    # Maximum spend per time window
    max_usd_per_minute: Optional[float] = None
    max_usd_per_hour: Optional[float] = None
    max_usd_per_day: Optional[float] = None
    
    # Maximum tokens per time window
    max_tokens_per_minute: Optional[int] = None
    max_tokens_per_hour: Optional[int] = None
    
    # Maximum API calls per time window
    max_calls_per_minute: Optional[int] = None
    max_calls_per_hour: Optional[int] = None
    
    def has_limits(self) -> bool:
        """Check if any limits are set"""
        return any([
            self.max_usd_per_minute is not None,
            self.max_usd_per_hour is not None,
            self.max_usd_per_day is not None,
            self.max_tokens_per_minute is not None,
            self.max_tokens_per_hour is not None,
            self.max_calls_per_minute is not None,
            self.max_calls_per_hour is not None,
        ])


@dataclass
class UsageEvent:
    """Single usage event with timestamp"""
    timestamp: datetime
    cost_usd: float
    tokens: int
    api_calls: int


class BurnRateLimiter:
    """
    Burn rate limiter with sliding window
    
    Prevents spending too fast by tracking usage over time windows
    
    Example:
        limiter = BurnRateLimiter(
            max_usd_per_minute=0.10,  # Max $0.10/minute
            max_usd_per_hour=5.0,     # Max $5/hour
        )
        
        limiter.check_and_record(usage)  # Raises if would exceed rate
    """
    
    def __init__(
        self,
        max_usd_per_minute: Optional[float] = None,
        max_usd_per_hour: Optional[float] = None,
        max_usd_per_day: Optional[float] = None,
        max_tokens_per_minute: Optional[int] = None,
        max_tokens_per_hour: Optional[int] = None,
        max_calls_per_minute: Optional[int] = None,
        max_calls_per_hour: Optional[int] = None,
    ):
        """
        Args:
            max_usd_per_minute: Maximum USD spend per minute
            max_usd_per_hour: Maximum USD spend per hour
            max_usd_per_day: Maximum USD spend per day
            max_tokens_per_minute: Maximum tokens per minute
            max_tokens_per_hour: Maximum tokens per hour
            max_calls_per_minute: Maximum API calls per minute
            max_calls_per_hour: Maximum API calls per hour
        """
        self.config = BurnRateConfig(
            max_usd_per_minute=max_usd_per_minute,
            max_usd_per_hour=max_usd_per_hour,
            max_usd_per_day=max_usd_per_day,
            max_tokens_per_minute=max_tokens_per_minute,
            max_tokens_per_hour=max_tokens_per_hour,
            max_calls_per_minute=max_calls_per_minute,
            max_calls_per_hour=max_calls_per_hour,
        )
        
        # Event history (sliding windows)
        self.events: Deque[UsageEvent] = deque()
        
        # Thread safety
        self._lock = Lock()
    
    def check_and_record(
        self,
        usage: CostUsage,
        now: Optional[datetime] = None,
    ) -> None:
        """
        Check if usage would exceed burn rate, then record it
        
        Args:
            usage: Usage to check
            now: Current time (for testing)
        
        Raises:
            FailCoreError: If burn rate exceeded
        """
        if not self.config.has_limits():
            return  # No limits configured
        
        with self._lock:
            now = now or datetime.now(timezone.utc)
            
            # Clean old events
            self._cleanup_old_events(now)
            
            # Check limits
            self._check_limits(usage, now)
            
            # Record event
            event = UsageEvent(
                timestamp=now,
                cost_usd=usage.cost_usd,
                tokens=usage.total_tokens,
                api_calls=usage.api_calls,
            )
            self.events.append(event)
    
    def _cleanup_old_events(self, now: datetime) -> None:
        """Remove events outside all time windows"""
        # Keep events from last 24 hours (max window)
        cutoff = now - timedelta(days=1)
        
        while self.events and self.events[0].timestamp < cutoff:
            self.events.popleft()
    
    def _check_limits(self, usage: CostUsage, now: datetime) -> None:
        """Check if adding usage would exceed any limit"""
        # Calculate usage in different time windows
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Aggregate current usage
        usd_per_minute = sum(e.cost_usd for e in self.events if e.timestamp >= minute_ago)
        usd_per_hour = sum(e.cost_usd for e in self.events if e.timestamp >= hour_ago)
        usd_per_day = sum(e.cost_usd for e in self.events if e.timestamp >= day_ago)
        
        tokens_per_minute = sum(e.tokens for e in self.events if e.timestamp >= minute_ago)
        tokens_per_hour = sum(e.tokens for e in self.events if e.timestamp >= hour_ago)
        
        calls_per_minute = sum(e.api_calls for e in self.events if e.timestamp >= minute_ago)
        calls_per_hour = sum(e.api_calls for e in self.events if e.timestamp >= hour_ago)
        
        # Check USD limits
        if self.config.max_usd_per_minute is not None:
            if usd_per_minute + usage.cost_usd > self.config.max_usd_per_minute:
                self._raise_limit_exceeded(
                    "USD per minute",
                    usd_per_minute,
                    self.config.max_usd_per_minute,
                    usage.cost_usd,
                )
        
        if self.config.max_usd_per_hour is not None:
            if usd_per_hour + usage.cost_usd > self.config.max_usd_per_hour:
                self._raise_limit_exceeded(
                    "USD per hour",
                    usd_per_hour,
                    self.config.max_usd_per_hour,
                    usage.cost_usd,
                )
        
        if self.config.max_usd_per_day is not None:
            if usd_per_day + usage.cost_usd > self.config.max_usd_per_day:
                self._raise_limit_exceeded(
                    "USD per day",
                    usd_per_day,
                    self.config.max_usd_per_day,
                    usage.cost_usd,
                )
        
        # Check token limits
        if self.config.max_tokens_per_minute is not None:
            if tokens_per_minute + usage.total_tokens > self.config.max_tokens_per_minute:
                self._raise_limit_exceeded(
                    "tokens per minute",
                    tokens_per_minute,
                    self.config.max_tokens_per_minute,
                    usage.total_tokens,
                    unit="tokens",
                )
        
        if self.config.max_tokens_per_hour is not None:
            if tokens_per_hour + usage.total_tokens > self.config.max_tokens_per_hour:
                self._raise_limit_exceeded(
                    "tokens per hour",
                    tokens_per_hour,
                    self.config.max_tokens_per_hour,
                    usage.total_tokens,
                    unit="tokens",
                )
        
        # Check API call limits
        if self.config.max_calls_per_minute is not None:
            if calls_per_minute + usage.api_calls > self.config.max_calls_per_minute:
                self._raise_limit_exceeded(
                    "API calls per minute",
                    calls_per_minute,
                    self.config.max_calls_per_minute,
                    usage.api_calls,
                    unit="calls",
                )
        
        if self.config.max_calls_per_hour is not None:
            if calls_per_hour + usage.api_calls > self.config.max_calls_per_hour:
                self._raise_limit_exceeded(
                    "API calls per hour",
                    calls_per_hour,
                    self.config.max_calls_per_hour,
                    usage.api_calls,
                    unit="calls",
                )
    
    def _raise_limit_exceeded(
        self,
        limit_name: str,
        current: float,
        maximum: float,
        requested: float,
        unit: str = "USD",
    ) -> None:
        """Raise error for exceeded burn rate"""
        raise FailCoreError(
            message=f"Burn rate exceeded: {limit_name} limit",
            error_code=codes.ECONOMIC_BUDGET_EXCEEDED,
            phase="BURN_RATE_CHECK",
            suggestion=(
                f"Spending too fast. Current rate: {current:.4f} {unit}, "
                f"limit: {maximum:.4f} {unit}. "
                f"Wait a moment before retrying, or increase burn rate limit."
            ),
            details={
                "limit_name": limit_name,
                "current_usage": current,
                "limit": maximum,
                "requested": requested,
                "unit": unit,
            }
        )
    
    def get_current_rates(self) -> dict:
        """Get current burn rates across all windows"""
        with self._lock:
            now = datetime.now(timezone.utc)
            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(days=1)
            
            return {
                "usd_per_minute": sum(e.cost_usd for e in self.events if e.timestamp >= minute_ago),
                "usd_per_hour": sum(e.cost_usd for e in self.events if e.timestamp >= hour_ago),
                "usd_per_day": sum(e.cost_usd for e in self.events if e.timestamp >= day_ago),
                "tokens_per_minute": sum(e.tokens for e in self.events if e.timestamp >= minute_ago),
                "tokens_per_hour": sum(e.tokens for e in self.events if e.timestamp >= hour_ago),
                "calls_per_minute": sum(e.api_calls for e in self.events if e.timestamp >= minute_ago),
                "calls_per_hour": sum(e.api_calls for e in self.events if e.timestamp >= hour_ago),
                "total_events": len(self.events),
            }


__all__ = [
    "BurnRateConfig",
    "BurnRateLimiter",
]
