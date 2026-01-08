"""
P0-3: Remote Retry Policy
Only retry transient errors (timeout, unreachable, server error)
Never retry validation/parameter errors
"""

from dataclasses import dataclass
from typing import Set
import random


@dataclass
class RetryPolicy:
    """
    Retry policy for remote tool calls
    
    Key principle: Only retry TRANSIENT errors
    - REMOTE_TIMEOUT ✓
    - REMOTE_UNREACHABLE ✓
    - REMOTE_SERVER_ERROR ✓ (if retryable=True)
    - REMOTE_INVALID_PARAMS ✗ (never retry)
    - REMOTE_TOOL_NOT_FOUND ✗ (never retry)
    - REMOTE_PROTOCOL_MISMATCH ✗ (never retry)
    """
    
    max_attempts: int = 3
    base_delay_ms: int = 1000  # 1 second
    max_delay_ms: int = 30000  # 30 seconds
    jitter_factor: float = 0.2  # ±20% randomness
    
    # Error codes that are retryable
    retry_on_codes: Set[str] = None
    
    def __post_init__(self):
        if self.retry_on_codes is None:
            from failcore.core.errors import codes
            self.retry_on_codes = {
                codes.REMOTE_TIMEOUT,
                codes.REMOTE_UNREACHABLE,
                codes.REMOTE_SERVER_ERROR,
            }
    
    def should_retry(self, error_code: str, retryable: bool = False) -> bool:
        """
        Decide if error should be retried
        
        Args:
            error_code: Error code from ToolResult.error
            retryable: Explicit retryable flag from error
        
        Returns:
            True if should retry
        """
        # Never retry if explicitly marked as non-retryable
        if retryable is False:
            return False
        
        # Only retry transient error codes
        return error_code in self.retry_on_codes
    
    def get_delay_ms(self, attempt: int) -> int:
        """
        Calculate exponential backoff delay with jitter
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in milliseconds
        """
        # Exponential backoff: base * 2^attempt
        delay = self.base_delay_ms * (2 ** attempt)
        
        # Cap at max delay
        delay = min(delay, self.max_delay_ms)
        
        # Add jitter (±jitter_factor)
        jitter = delay * self.jitter_factor
        delay += random.uniform(-jitter, jitter)
        
        return int(max(0, delay))
    
    @classmethod
    def disabled(cls):
        """No retry policy"""
        return cls(max_attempts=1)
    
    @classmethod
    def aggressive(cls):
        """Aggressive retry for flaky networks"""
        return cls(
            max_attempts=5,
            base_delay_ms=500,
            max_delay_ms=60000,
            jitter_factor=0.3,
        )


__all__ = ["RetryPolicy"]
