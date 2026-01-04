"""
Cost Guardrails - Estimator

Estimate cost before tool execution (for circuit breaker)
"""

from typing import Dict, Any, Optional
from .models import CostUsage


class CostEstimator:
    """
    Estimate tool execution cost
    
    Supports:
    - LLM token-based pricing (per-token)
    - API call flat rate
    - Custom estimators per tool
    """
    
    # Default pricing (USD per 1K tokens, as of 2024)
    DEFAULT_PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    }
    
    def __init__(self, pricing: Dict[str, Dict[str, float]] = None):
        """
        Args:
            pricing: Custom pricing dict {model: {"input": price, "output": price}}
                    Prices are per 1K tokens in USD
        """
        self.pricing = pricing or self.DEFAULT_PRICING
    
    def estimate_llm_cost(
        self,
        tool_name: str,
        params: Dict[str, Any],
        model: str = "gpt-4",
        estimated_input_tokens: int = None,
        estimated_output_tokens: int = None,
    ) -> CostUsage:
        """
        Estimate cost for LLM tool call
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            model: LLM model name
            estimated_input_tokens: Estimated input tokens (if known)
            estimated_output_tokens: Estimated output tokens (if known)
        
        Returns:
            CostUsage with estimated cost
        """
        # Estimate tokens if not provided
        if estimated_input_tokens is None:
            estimated_input_tokens = self._estimate_input_tokens(params)
        
        if estimated_output_tokens is None:
            estimated_output_tokens = self._estimate_output_tokens(tool_name, params)
        
        total_tokens = estimated_input_tokens + estimated_output_tokens
        
        # Calculate cost
        cost_usd = 0.0
        if model in self.pricing:
            pricing = self.pricing[model]
            cost_usd = (
                (estimated_input_tokens / 1000.0) * pricing.get("input", 0.0) +
                (estimated_output_tokens / 1000.0) * pricing.get("output", 0.0)
            )
        
        return CostUsage(
            run_id="",  # Will be filled by caller
            step_id="",  # Will be filled by caller
            tool_name=tool_name,
            input_tokens=estimated_input_tokens,
            output_tokens=estimated_output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            estimated=True,
            api_calls=1,
            model=model,
        )
    
    def estimate_api_cost(
        self,
        tool_name: str,
        params: Dict[str, Any],
        cost_per_call: float = 0.001,  # $0.001 per call default
    ) -> CostUsage:
        """
        Estimate cost for API tool call (flat rate)
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            cost_per_call: Flat cost per API call in USD
        
        Returns:
            CostUsage with estimated cost
        """
        return CostUsage(
            run_id="",
            step_id="",
            tool_name=tool_name,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost_usd=cost_per_call,
            estimated=True,
            api_calls=1,
        )
    
    def _estimate_input_tokens(self, params: Dict[str, Any]) -> int:
        """
        Estimate input tokens from parameters
        
        Simple heuristic: 1 token ≈ 4 characters
        """
        import json
        params_str = json.dumps(params, default=str)
        return len(params_str) // 4
    
    def _estimate_output_tokens(self, tool_name: str, params: Dict[str, Any]) -> int:
        """
        Estimate output tokens
        
        Simple heuristic based on tool type
        """
        # Tool-specific estimates
        if "generate" in tool_name.lower() or "write" in tool_name.lower():
            return 500  # Generative tools produce more output
        elif "search" in tool_name.lower() or "query" in tool_name.lower():
            return 300  # Search tools produce medium output
        else:
            return 100  # Default: small output
    
    def estimate(
        self,
        tool_name: str,
        params: Dict[str, Any],
        metadata: Dict[str, Any] = None,
        actual_usage: Optional[CostUsage] = None,
    ) -> CostUsage:
        """
        Estimate cost for any tool with priority hierarchy
        
        Priority (highest to lowest):
        1. actual_usage: Real usage from provider (estimated=False)
        2. metadata["cost_usd"]: Explicit cost override
        3. metadata["cost_per_call"]: Flat rate per call
        4. metadata["model"]: LLM model-based estimation
        5. Default: minimal cost
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            metadata: Tool metadata (risk, effect, model, cost overrides, etc.)
            actual_usage: Real usage from tool execution (if available)
        
        Returns:
            CostUsage with estimated or actual cost
        """
        metadata = metadata or {}
        
        # Priority 1: Use actual usage if provided
        if actual_usage:
            return actual_usage
        
        # Priority 2: Explicit cost override (deterministic for testing)
        if "cost_usd" in metadata:
            # Support both "tokens" and "total_tokens"
            total_tokens = metadata.get("total_tokens", metadata.get("tokens", 0))
            input_tokens = metadata.get("input_tokens", 0)
            output_tokens = metadata.get("output_tokens", 0)
            
            # If only total_tokens provided, leave input/output as 0
            # If total_tokens not provided but input/output are, calculate total
            if not total_tokens and (input_tokens or output_tokens):
                total_tokens = input_tokens + output_tokens
            
            return CostUsage(
                run_id="",
                step_id="",
                tool_name=tool_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=float(metadata["cost_usd"]),
                estimated=True,
                api_calls=1,
                model=metadata.get("model"),
                provider=metadata.get("provider"),
            )
        
        # Priority 3: Flat rate per call
        if "cost_per_call" in metadata:
            return self.estimate_api_cost(
                tool_name,
                params,
                cost_per_call=float(metadata["cost_per_call"])
            )
        
        # Priority 4: LLM model-based estimation
        if "model" in metadata:
            return self.estimate_llm_cost(
                tool_name,
                params,
                model=metadata["model"],
                estimated_input_tokens=metadata.get("input_tokens"),
                estimated_output_tokens=metadata.get("output_tokens"),
            )
        
        # Priority 5: Default minimal cost
        return CostUsage(
            run_id="",
            step_id="",
            tool_name=tool_name,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost_usd=0.0001,  # $0.0001 default
            estimated=True,
            api_calls=1,
        )


__all__ = ["CostEstimator"]
