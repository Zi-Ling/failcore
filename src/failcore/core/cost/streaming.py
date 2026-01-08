"""
Streaming Token Watchdog

Real-time token consumption monitoring for streaming LLM responses
Prevents budget overruns during generation
"""

from typing import Optional, Callable, Any
from threading import Lock
from .models import CostUsage, Budget
from ..errors import FailCoreError, codes


class StreamingTokenWatchdog:
    """
    Monitor token consumption in real-time during streaming
    
    Critical for LLM streaming where output length is unknown.
    Interrupts generation when budget limit is approached.
    
    Usage:
        watchdog = StreamingTokenWatchdog(budget, check_interval=100)
        
        for chunk in stream:
            tokens = count_tokens(chunk)
            watchdog.on_token_generated(tokens)  # May raise if over budget
    """
    
    def __init__(
        self,
        budget: Budget,
        check_interval: int = 100,
        safety_margin: float = 0.95,  # Stop at 95% to leave buffer
        cost_per_1k_output_tokens: float = 0.03,  # Default GPT-4 output price
    ):
        """
        Args:
            budget: Budget to enforce
            check_interval: Check budget every N tokens
            safety_margin: Stop at this % of budget (0.0-1.0)
            cost_per_1k_output_tokens: Price for output tokens (USD per 1K)
        """
        self.budget = budget
        self.check_interval = check_interval
        self.safety_margin = safety_margin
        self.cost_per_1k_output_tokens = cost_per_1k_output_tokens
        
        # State
        self.tokens_generated = 0
        self.tokens_since_last_check = 0
        self.is_interrupted = False
        
        # Thread safety
        self._lock = Lock()
    
    def on_token_generated(
        self,
        token_count: int = 1,
        run_id: str = "",
        step_id: str = "",
    ) -> None:
        """
        Called when tokens are generated
        
        Args:
            token_count: Number of tokens generated
            run_id: Current run ID
            step_id: Current step ID
        
        Raises:
            FailCoreError: If budget exceeded
        """
        with self._lock:
            self.tokens_generated += token_count
            self.tokens_since_last_check += token_count
            
            # Check budget at intervals
            if self.tokens_since_last_check >= self.check_interval:
                self._check_budget(run_id, step_id)
                self.tokens_since_last_check = 0
    
    def _check_budget(self, run_id: str, step_id: str) -> None:
        """Check if budget is exceeded"""
        if self.is_interrupted:
            return  # Already interrupted
        
        # Create usage for current generation
        cost_usd = (self.tokens_generated / 1000.0) * self.cost_per_1k_output_tokens
        
        usage = CostUsage(
            run_id=run_id,
            step_id=step_id,
            tool_name="streaming_generation",
            output_tokens=self.tokens_generated,
            total_tokens=self.tokens_generated,
            cost_usd=cost_usd,
            estimated=True,  # Streaming estimate (will be corrected by provider usage if available)
            source="streaming",  # Mark as streaming source
        )
        
        # Check against budget
        would_exceed, reason, error_code = self.budget.would_exceed(usage)
        
        # Also check if we're approaching limit (safety margin)
        usage_pct = self.budget.usage_percentage()
        if usage_pct >= self.safety_margin:
            would_exceed = True
            reason = f"Approaching budget limit ({usage_pct:.0%} used, safety margin: {self.safety_margin:.0%})"
        
        if would_exceed:
            self.is_interrupted = True
            raise FailCoreError(
                message=f"Streaming interrupted: {reason}",
                error_code=codes.ECONOMIC_BUDGET_EXCEEDED,
                phase="STREAMING_GENERATION",
                suggestion=(
                    f"Budget limit reached during streaming generation. "
                    f"Generated {self.tokens_generated} tokens before interruption. "
                    f"Consider: increase budget or reduce max_tokens parameter."
                ),
                details={
                    "tokens_generated": self.tokens_generated,
                    "cost_usd": cost_usd,
                    "budget_used_pct": usage_pct,
                    "safety_margin": self.safety_margin,
                }
            )
    
    def finalize(self) -> int:
        """
        Finalize and return total tokens generated
        
        Call this after stream completes successfully
        """
        with self._lock:
            return self.tokens_generated
    
    def get_stats(self) -> dict:
        """Get watchdog statistics"""
        with self._lock:
            return {
                "tokens_generated": self.tokens_generated,
                "is_interrupted": self.is_interrupted,
                "cost_usd": (self.tokens_generated / 1000.0) * self.cost_per_1k_output_tokens,
            }


class StreamingCostGuard:
    """
    High-level streaming cost guard
    
    Simpler interface for common use cases
    """
    
    def __init__(
        self,
        max_cost_usd: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: str = "gpt-4",
    ):
        """
        Args:
            max_cost_usd: Maximum cost for this stream
            max_tokens: Maximum tokens for this stream
            model: Model name (for pricing lookup)
        """
        # Create budget
        self.budget = Budget(
            max_cost_usd=max_cost_usd,
            max_tokens=max_tokens,
        )
        
        # Create watchdog
        # TODO: Get price from DynamicPriceEngine
        self.watchdog = StreamingTokenWatchdog(
            budget=self.budget,
            check_interval=50,  # Check every 50 tokens
            safety_margin=0.95,
        )
    
    def on_chunk(
        self,
        chunk: Any,
        token_counter: Optional[Callable[[Any], int]] = None,
    ) -> None:
        """
        Process streaming chunk
        
        Args:
            chunk: Stream chunk (text or delta)
            token_counter: Function to count tokens in chunk
        
        Raises:
            FailCoreError: If budget exceeded
        """
        # Count tokens
        if token_counter:
            token_count = token_counter(chunk)
        else:
            # Simple heuristic: ~4 chars per token
            token_count = max(1, len(str(chunk)) // 4)
        
        # Check budget
        self.watchdog.on_token_generated(token_count)
    
    def get_total_tokens(self) -> int:
        """Get total tokens generated"""
        return self.watchdog.finalize()


__all__ = [
    "StreamingTokenWatchdog",
    "StreamingCostGuard",
]
