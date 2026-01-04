# failcore/core/cost/usage.py
"""
Usage Extractor

Extract real usage information from tool return values
Supports multiple tool return formats (LLM provider, API responses, etc.)
"""

from typing import Any, Optional, Dict
from .models import CostUsage


class UsageExtractor:
    """
    Extract usage information from tool return values

    Supported formats:
    1. Dict with "usage" key: {"result": ..., "usage": {...}}
    2. Object with .usage attribute
    3. OpenAI-style response: response.usage
    4. Anthropic-style response: response.usage
    """

    @staticmethod
    def extract(
            tool_output: Any,
            run_id: str,
            step_id: str,
            tool_name: str,
    ) -> Optional[CostUsage]:
        """
        Try to extract usage from tool output

        Args:
            tool_output: Tool return value
            run_id: Run ID
            step_id: Step ID
            tool_name: Tool name

        Returns:
            CostUsage if extracted, None otherwise
        """
        usage_data = None

        # Case 1: Dict with "usage" key
        if isinstance(tool_output, dict) and "usage" in tool_output:
            usage_data = tool_output["usage"]

        # Case 2: Object with .usage attribute
        elif hasattr(tool_output, "usage"):
            usage_data = tool_output.usage
            # If it's an object, try to convert to dict
            if not isinstance(usage_data, dict):
                # First try vars() (for normal objects with __dict__)
                usage_dict = {}
                if hasattr(usage_data, "__dict__"):
                    usage_dict = vars(usage_data)

                # If vars() returns empty, try extracting attributes manually
                if not usage_dict:
                    for attr in ['prompt_tokens', 'completion_tokens', 'total_tokens',
                                 'input_tokens', 'output_tokens', 'cost_usd', 'model', 'provider']:
                        if hasattr(usage_data, attr):
                            usage_dict[attr] = getattr(usage_data, attr)

                if usage_dict:
                    usage_data = usage_dict

        # Case 3: Object with ._usage attribute (some providers)
        elif hasattr(tool_output, "_usage"):
            usage_data = tool_output._usage
            if hasattr(usage_data, "__dict__"):
                usage_data = vars(usage_data)

        if not usage_data:
            return None

        # Parse usage data (handle different formats)
        return UsageExtractor._parse_usage_data(
            usage_data,
            run_id,
            step_id,
            tool_name,
        )

    @staticmethod
    def _parse_usage_data(
            usage_data: Any,
            run_id: str,
            step_id: str,
            tool_name: str,
    ) -> Optional[CostUsage]:
        """
        Parse usage data to CostUsage

        Supported formats:
        - OpenAI: {prompt_tokens, completion_tokens, total_tokens}
        - Anthropic: {input_tokens, output_tokens}
        - Generic: {input_tokens, output_tokens, total_tokens, cost_usd}
        """
        if isinstance(usage_data, dict):
            # Extract token counts (handle different naming conventions)
            input_tokens = (
                    usage_data.get("input_tokens") or
                    usage_data.get("prompt_tokens") or
                    0
            )
            output_tokens = (
                    usage_data.get("output_tokens") or
                    usage_data.get("completion_tokens") or
                    0
            )
            total_tokens = (
                    usage_data.get("total_tokens") or
                    (input_tokens + output_tokens)
            )

            # Extract cost (if provided)
            cost_usd = usage_data.get("cost_usd", 0.0)

            # Extract model/provider info
            model = usage_data.get("model")
            provider = usage_data.get("provider")

            return CostUsage(
                run_id=run_id,
                step_id=step_id,
                tool_name=tool_name,
                model=model,
                provider=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                estimated=False,  # Real usage from provider
                api_calls=1,
            )

        return None


__all__ = ["UsageExtractor"]