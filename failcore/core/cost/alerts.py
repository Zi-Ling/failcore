"""
Budget Alerts

Multi-level warnings for budget usage
Provides early warning before hard limits
"""

from typing import Optional, Callable, List
from enum import Enum
from dataclasses import dataclass

from .models import Budget, CostUsage


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"        # Informational (< 50%)
    WARNING = "warning"  # Warning (50-80%)
    CRITICAL = "critical"  # Critical (80-95%)
    URGENT = "urgent"    # Urgent (95-100%)
    EXCEEDED = "exceeded"  # Over budget


@dataclass
class BudgetAlert:
    """Budget alert notification"""
    level: AlertLevel
    message: str
    usage_percentage: float  # 0.0 - 1.0
    details: dict


class BudgetAlertManager:
    """
    Multi-level budget alert system
    
    Provides graduated warnings:
    - 50%: INFO - "Budget half used"
    - 80%: WARNING - "Approaching budget limit"
    - 90%: CRITICAL - "Budget nearly exhausted"
    - 95%: URGENT - "Budget almost exceeded"
    - 100%: EXCEEDED - "Budget exceeded"
    
    Example:
        manager = BudgetAlertManager(budget)
        manager.on_usage(usage)  # Triggers appropriate alert
    """
    
    # Alert thresholds
    THRESHOLDS = {
        AlertLevel.WARNING: 0.80,   # 80%
        AlertLevel.CRITICAL: 0.90,  # 90%
        AlertLevel.URGENT: 0.95,    # 95%
        AlertLevel.EXCEEDED: 1.0,   # 100%
    }
    
    def __init__(
        self,
        budget: Budget,
        on_alert: Optional[Callable[[BudgetAlert], None]] = None,
        custom_thresholds: Optional[dict] = None,
    ):
        """
        Args:
            budget: Budget to monitor
            on_alert: Callback for alerts
            custom_thresholds: Custom alert thresholds {AlertLevel: percentage}
        """
        self.budget = budget
        self.on_alert = on_alert
        self.thresholds = custom_thresholds or self.THRESHOLDS
        
        # Track what's been alerted
        self.alerted_levels: set = set()
        
        # Alert history
        self.alert_history: List[BudgetAlert] = []
    
    def check_budget(
        self,
        usage: Optional[CostUsage] = None,
    ) -> Optional[BudgetAlert]:
        """
        Check budget and return alert if threshold crossed
        
        Args:
            usage: New usage (will be added to budget temporarily)
        
        Returns:
            Alert if threshold crossed, None otherwise
        """
        # Calculate current usage percentage
        if usage:
            # Simulate adding usage
            temp_budget = Budget(
                max_cost_usd=self.budget.max_cost_usd,
                max_tokens=self.budget.max_tokens,
                max_api_calls=self.budget.max_api_calls,
                used_cost_usd=self.budget.used_cost_usd + usage.cost_usd,
                used_tokens=self.budget.used_tokens + usage.total_tokens,
                used_api_calls=self.budget.used_api_calls + usage.api_calls,
            )
            usage_pct = temp_budget.usage_percentage()
        else:
            usage_pct = self.budget.usage_percentage()
        
        # Determine alert level
        alert_level = self._get_alert_level(usage_pct)
        
        # Check if we should alert for this level
        if alert_level and alert_level not in self.alerted_levels:
            # Generate alert
            alert = self._create_alert(alert_level, usage_pct, usage)
            
            # Mark as alerted
            self.alerted_levels.add(alert_level)
            
            # Record in history
            self.alert_history.append(alert)
            
            # Trigger callback
            if self.on_alert:
                self.on_alert(alert)
            
            return alert
        
        return None
    
    def _get_alert_level(self, usage_pct: float) -> Optional[AlertLevel]:
        """Determine alert level based on usage percentage"""
        if usage_pct >= self.thresholds[AlertLevel.EXCEEDED]:
            return AlertLevel.EXCEEDED
        elif usage_pct >= self.thresholds[AlertLevel.URGENT]:
            return AlertLevel.URGENT
        elif usage_pct >= self.thresholds[AlertLevel.CRITICAL]:
            return AlertLevel.CRITICAL
        elif usage_pct >= self.thresholds[AlertLevel.WARNING]:
            return AlertLevel.WARNING
        else:
            return None
    
    def _create_alert(
        self,
        level: AlertLevel,
        usage_pct: float,
        usage: Optional[CostUsage],
    ) -> BudgetAlert:
        """Create alert with appropriate message"""
        # Build message
        if level == AlertLevel.WARNING:
            message = f"⚠️  Budget warning: {usage_pct:.0%} used"
            suggestion = "Monitor usage closely"
        elif level == AlertLevel.CRITICAL:
            message = f"🔴 Budget critical: {usage_pct:.0%} used"
            suggestion = "Budget nearly exhausted - consider increasing limits"
        elif level == AlertLevel.URGENT:
            message = f"🚨 Budget urgent: {usage_pct:.0%} used"
            suggestion = "Budget about to be exceeded - operations may be blocked soon"
        else:  # EXCEEDED
            message = f"❌ Budget exceeded: {usage_pct:.0%} used"
            suggestion = "Budget limit reached - operations will be blocked"
        
        # Build details
        details = {
            "usage_percentage": usage_pct,
            "budget": self.budget.to_dict(),
            "suggestion": suggestion,
        }
        
        if usage:
            details["triggering_usage"] = usage.to_dict()
        
        # Add specific limit details
        if self.budget.max_cost_usd:
            details["usd"] = {
                "used": self.budget.used_cost_usd,
                "limit": self.budget.max_cost_usd,
                "remaining": self.budget.remaining_cost_usd(),
            }
        
        if self.budget.max_tokens:
            details["tokens"] = {
                "used": self.budget.used_tokens,
                "limit": self.budget.max_tokens,
                "remaining": self.budget.remaining_tokens(),
            }
        
        if self.budget.max_api_calls:
            details["api_calls"] = {
                "used": self.budget.used_api_calls,
                "limit": self.budget.max_api_calls,
                "remaining": self.budget.remaining_api_calls(),
            }
        
        return BudgetAlert(
            level=level,
            message=message,
            usage_percentage=usage_pct,
            details=details,
        )
    
    def reset(self) -> None:
        """Reset alert tracking (for new budget period)"""
        self.alerted_levels.clear()
        self.alert_history.clear()
    
    def get_alert_summary(self) -> dict:
        """Get summary of all alerts"""
        return {
            "total_alerts": len(self.alert_history),
            "alerted_levels": [level.value for level in self.alerted_levels],
            "current_usage": self.budget.usage_percentage(),
            "alerts": [
                {
                    "level": alert.level.value,
                    "message": alert.message,
                    "usage_pct": alert.usage_percentage,
                }
                for alert in self.alert_history
            ],
        }


class SimpleAlertLogger:
    """Simple alert logger that prints to console"""
    
    def __call__(self, alert: BudgetAlert) -> None:
        """Log alert"""
        print(f"\n{alert.message}")
        print(f"Usage: {alert.usage_percentage:.1%}")
        if "suggestion" in alert.details:
            print(f"Suggestion: {alert.details['suggestion']}")


__all__ = [
    "AlertLevel",
    "BudgetAlert",
    "BudgetAlertManager",
    "SimpleAlertLogger",
]
