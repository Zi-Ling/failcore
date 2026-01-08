"""
Cost Guardian - Unified Global Protection

Integrated cost protection manager that coordinates all cost control features.
Provides simple facade for comprehensive economic safety.
"""

from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import Budget, CostUsage, BudgetScope
from .pricing import DynamicPriceEngine, PriceProvider
from .streaming import StreamingTokenWatchdog
from .ratelimit import BurnRateLimiter, UsageEvent
from .alerts import BudgetAlertManager, AlertLevel, BudgetAlert


@dataclass
class GuardianConfig:
    """
    Unified configuration for Cost Guardian
    
    Simplifies setup of all cost protection features
    """
    # Budget limits
    max_cost_usd: Optional[float] = None
    max_tokens: Optional[int] = None
    max_api_calls: Optional[int] = None
    
    # Burn rate limits
    max_usd_per_minute: Optional[float] = None
    max_usd_per_hour: Optional[float] = None
    max_tokens_per_minute: Optional[int] = None
    max_calls_per_minute: Optional[int] = None
    
    # Alert thresholds (can override defaults)
    alert_at_80_percent: bool = True
    alert_at_90_percent: bool = True
    alert_at_95_percent: bool = True
    
    # Streaming watchdog
    streaming_check_interval: int = 100
    streaming_safety_margin: float = 0.95
    
    # Pricing
    enable_dynamic_pricing: bool = True
    enable_api_pricing: bool = False
    api_pricing_url: Optional[str] = None
    
    def has_budget_limits(self) -> bool:
        """Check if any budget limits are set"""
        return any([
            self.max_cost_usd is not None,
            self.max_tokens is not None,
            self.max_api_calls is not None,
        ])
    
    def has_burn_rate_limits(self) -> bool:
        """Check if any burn rate limits are set"""
        return any([
            self.max_usd_per_minute is not None,
            self.max_usd_per_hour is not None,
            self.max_tokens_per_minute is not None,
            self.max_calls_per_minute is not None,
        ])


class CostGuardian:
    """
    Unified Cost Guardian
    
    Integrates all cost protection features into a single, easy-to-use interface.
    
    Features:
    - Budget enforcement
    - Burn rate limiting
    - Multi-level alerts
    - Streaming token watchdog
    - Dynamic pricing
    
    Example:
        # Simple setup
        guardian = CostGuardian(
            max_cost_usd=10.0,
            max_usd_per_minute=0.50,
        )
        
        # Check before operation
        guardian.check_operation(usage)
        
        # Monitor streaming
        watchdog = guardian.create_streaming_watchdog()
        for chunk in stream:
            watchdog.on_token_generated(tokens)
    """
    
    def __init__(
        self,
        config: Optional[GuardianConfig] = None,
        # Quick setup shortcuts
        max_cost_usd: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_usd_per_minute: Optional[float] = None,
        # Callbacks
        on_alert: Optional[Callable[[BudgetAlert], None]] = None,
        on_budget_exceeded: Optional[Callable[[str], None]] = None,
        on_burn_rate_exceeded: Optional[Callable[[str], None]] = None,
        # Custom components
        price_provider: Optional[PriceProvider] = None,
    ):
        """
        Args:
            config: Full configuration object
            max_cost_usd: Quick setup - max USD
            max_tokens: Quick setup - max tokens
            max_usd_per_minute: Quick setup - burn rate
            on_alert: Alert callback
            on_budget_exceeded: Budget exceeded callback
            on_burn_rate_exceeded: Burn rate exceeded callback
            price_provider: Custom price provider
        """
        # Build config
        if config is None:
            config = GuardianConfig(
                max_cost_usd=max_cost_usd,
                max_tokens=max_tokens,
                max_usd_per_minute=max_usd_per_minute,
            )
        
        self.config = config
        
        # Callbacks
        self.on_alert = on_alert
        self.on_budget_exceeded = on_budget_exceeded
        self.on_burn_rate_exceeded = on_burn_rate_exceeded
        
        # Initialize components
        self._init_budget()
        self._init_pricing(price_provider)
        self._init_burn_limiter()
        self._init_alerts()
        
        # Statistics
        self.operations_checked = 0
        self.operations_blocked = 0
        self.alerts_triggered = 0
    
    def _init_budget(self):
        """Initialize budget"""
        if self.config.has_budget_limits():
            # Guardian-level budget is global (not tied to specific run)
            # Use ORG scope as it doesn't require run_id
            self.budget = Budget(
                budget_id="guardian-global",
                scope=BudgetScope.ORG,
                org_id="default",  # Default org for global guardian
                max_cost_usd=self.config.max_cost_usd,
                max_tokens=self.config.max_tokens,
                max_api_calls=self.config.max_api_calls,
            )
        else:
            self.budget = None
    
    def _init_pricing(self, price_provider: Optional[PriceProvider]):
        """Initialize pricing engine"""
        if self.config.enable_dynamic_pricing:
            self.pricing = DynamicPriceEngine(
                provider=price_provider,
                enable_env=True,
                enable_api=self.config.enable_api_pricing,
                api_url=self.config.api_pricing_url,
            )
        else:
            self.pricing = None
    
    def _init_burn_limiter(self):
        """Initialize burn rate limiter"""
        if self.config.has_burn_rate_limits():
            self.burn_limiter = BurnRateLimiter(
                max_usd_per_minute=self.config.max_usd_per_minute,
                max_usd_per_hour=self.config.max_usd_per_hour,
                max_tokens_per_minute=self.config.max_tokens_per_minute,
                max_calls_per_minute=self.config.max_calls_per_minute,
            )
        else:
            self.burn_limiter = None
    
    def _init_alerts(self):
        """Initialize alert manager"""
        if self.budget:
            self.alert_manager = BudgetAlertManager(
                budget=self.budget,
                on_alert=self._handle_alert,
            )
        else:
            self.alert_manager = None
    
    def _handle_alert(self, alert: BudgetAlert):
        """Handle budget alert"""
        self.alerts_triggered += 1
        
        if self.on_alert:
            self.on_alert(alert)
    
    def check_operation(
        self,
        usage: CostUsage,
        raise_on_exceed: bool = True,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if operation is allowed
        
        Coordinates all protection layers:
        1. Budget check
        2. Burn rate check
        3. Alert check
        
        Args:
            usage: Planned operation usage
            raise_on_exceed: Raise error if exceeded
        
        Returns:
            (allowed, reason, error_code) - True if allowed, False + reason + error_code if blocked
            error_code: "BURN_RATE_EXCEEDED", "BUDGET_COST_EXCEEDED", "BUDGET_TOKENS_EXCEEDED", etc.
        
        Raises:
            FailCoreError: If raise_on_exceed=True and limits exceeded
        """
        from ..errors import FailCoreError, codes
        
        self.operations_checked += 1
        
        # 1. Check burn rate (BEFORE budget check)
        if self.burn_limiter:
            try:
                self.burn_limiter.check_and_record(usage)
            except FailCoreError as e:
                self.operations_blocked += 1
                if self.on_burn_rate_exceeded:
                    self.on_burn_rate_exceeded(e.message)
                if raise_on_exceed:
                    raise
                # Return with specific burn rate message
                return (False, str(e.message), "BURN_RATE_EXCEEDED")
        
        # 2. Check budget
        if self.budget:
            would_exceed, reason, error_code = self.budget.would_exceed(usage)
            if would_exceed:
                self.operations_blocked += 1
                if self.on_budget_exceeded:
                    self.on_budget_exceeded(reason)
                if raise_on_exceed:
                    # Map specific error codes
                    if error_code == "BUDGET_COST_EXCEEDED":
                        code = codes.ECONOMIC_BUDGET_EXCEEDED
                    elif error_code == "BUDGET_TOKENS_EXCEEDED":
                        code = codes.ECONOMIC_TOKEN_LIMIT
                    elif error_code == "BUDGET_API_CALLS_EXCEEDED":
                        code = codes.ECONOMIC_BUDGET_EXCEEDED  # Use generic for now
                    else:
                        code = codes.ECONOMIC_BUDGET_EXCEEDED
                    
                    raise FailCoreError(
                        message=f"Budget exceeded: {reason}",
                        error_code=code,
                        phase="COST_GUARDIAN",
                        suggestion="Increase budget or reduce operation scope",
                        details={
                            "usage": usage.to_dict(),
                            "budget": self.budget.to_dict(),
                            "budget_error_code": error_code,
                        }
                    )
                return (False, reason, error_code)
        
        # 3. Check alerts (non-blocking)
        if self.alert_manager:
            self.alert_manager.check_budget(usage)
        
        return (True, None, None)
    
    def add_usage(self, usage: CostUsage) -> None:
        """
        Record actual usage after operation completes successfully.
        
        This updates:
        - Budget counters (used_cost_usd, used_tokens, used_api_calls)
        - Burn rate limiter history (for sliding window calculations)
        
        CRITICAL: This is called AFTER execution, using actual_usage (if extracted)
        or estimated_usage (if actual not available). This ensures budget counters
        and burn rate limiter reflect what was actually spent, not just what was estimated.
        
        IMPORTANT: Burn limiter records are updated here with actual cost, replacing
        the estimated value recorded during pre-check. This ensures burn rate calculations
        use the same cost source as budget and storage (final_usage).
        
        Args:
            usage: Actual usage from completed operation (final_usage from executor)
        """
        if self.budget:
            self.budget.add_usage(usage)
        
        # CRITICAL: Record actual usage to burn rate limiter
        # This replaces the estimated value recorded during pre-check (check_operation)
        # We use the same final_usage that budget and storage use, ensuring consistency
        if self.burn_limiter:
            now = datetime.now(timezone.utc)
            with self.burn_limiter._lock:
                # Remove the last event if it's from pre-check (very recent, < 2 seconds)
                # This ensures we replace estimated cost with actual cost
                if self.burn_limiter.events:
                    last_event = self.burn_limiter.events[-1]
                    # If last event is very recent, it's likely from pre-check
                    # Remove it and replace with actual usage
                    time_since_last = (now - last_event.timestamp).total_seconds()
                    if time_since_last < 2.0:  # Within 2 seconds, assume it's from pre-check
                        self.burn_limiter.events.pop()
                
                # Record actual usage with current timestamp
                # This ensures burn rate calculations use actual cost, not estimated
                event = UsageEvent(
                    timestamp=now,
                    cost_usd=usage.cost_usd,
                    tokens=usage.total_tokens,
                    api_calls=usage.api_calls,
                )
                self.burn_limiter.events.append(event)
    
    def create_streaming_watchdog(
        self,
        model: str = "gpt-4",
    ) -> StreamingTokenWatchdog:
        """
        Create streaming token watchdog
        
        Args:
            model: Model name for pricing
        
        Returns:
            Configured StreamingTokenWatchdog
        """
        if not self.budget:
            raise ValueError("Budget required for streaming watchdog")
        
        # Get output price
        output_price = 0.06  # Default GPT-4
        if self.pricing:
            output_price = self.pricing.get_price(model, "output")
        
        return StreamingTokenWatchdog(
            budget=self.budget,
            check_interval=self.config.streaming_check_interval,
            safety_margin=self.config.streaming_safety_margin,
            cost_per_1k_output_tokens=output_price,
        )
    
    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estimate cost for operation
        
        Uses dynamic pricing if available
        """
        if self.pricing:
            return self.pricing.calculate_cost(model, input_tokens, output_tokens)
        
        # Fallback to simple estimate
        return ((input_tokens + output_tokens) / 1000.0) * 0.03
    
    def get_status(self) -> Dict[str, Any]:
        """Get current guardian status"""
        status = {
            "operations_checked": self.operations_checked,
            "operations_blocked": self.operations_blocked,
            "alerts_triggered": self.alerts_triggered,
            "block_rate": self.operations_blocked / self.operations_checked if self.operations_checked > 0 else 0.0,
        }
        
        # Add budget info
        if self.budget:
            status["budget"] = {
                "usage_percentage": self.budget.usage_percentage(),
                "used_cost_usd": self.budget.used_cost_usd,
                "max_cost_usd": self.budget.max_cost_usd,
                "used_tokens": self.budget.used_tokens,
                "max_tokens": self.budget.max_tokens,
            }
        
        # Add burn rate info
        if self.burn_limiter:
            status["burn_rates"] = self.burn_limiter.get_current_rates()
        
        # Add alert info
        if self.alert_manager:
            status["alerts"] = self.alert_manager.get_alert_summary()
        
        return status
    
    def reset_budget(self):
        """Reset budget usage (for new period)"""
        if self.budget:
            self.budget.used_cost_usd = 0.0
            self.budget.used_tokens = 0
            self.budget.used_api_calls = 0
        
        if self.alert_manager:
            self.alert_manager.reset()


__all__ = [
    "GuardianConfig",
    "CostGuardian",
]
