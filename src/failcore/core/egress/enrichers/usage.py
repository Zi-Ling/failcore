# failcore/core/egress/enrichers/usage.py
"""
Usage Enricher - Extract usage information and add to EgressEvent

Unified cost/usage extraction for egress pipeline.
Input: usage-related payload inside event.evidence (prefer "tool_output")
Output: Standardized usage dict added to event.evidence["usage"]

Notes:
- Reuses failcore/core/cost/usage.py extraction logic
- Called by: EgressEngine during event enrichment phase
- Output consumed by: cost tracking, trace, audit systems
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from failcore.core.cost.usage import UsageExtractor
from ..types import EgressEvent, EgressType


class UsageEnricher:
    """
    Usage enricher for egress events.

    Responsibilities:
    - Extract usage from evidence payload (prefer tool_output; fall back to response/body if present)
    - Add standardized JSON-serializable usage dict to event.evidence["usage"]
    - Gracefully degrade on parse errors (optionally record usage_parse_error)

    Design:
    - Reuses existing UsageExtractor
    - Enriches COST and NETWORK events (proxy/network calls may carry model usage)
    - Defensive about evidence types and JSON serialization
    """

    def enrich(self, event: EgressEvent) -> None:
        """
        Enrich event with usage information.

        Modifies event.evidence["usage"] in-place when extraction succeeds.

        Args:
            event: EgressEvent to enrich
        """
        # Only enrich COST/NETWORK events (others won't carry model usage)
        if event.egress not in (EgressType.COST, EgressType.NETWORK):
            return

        # Defensive: evidence should be a dict
        evidence = getattr(event, "evidence", None)
        if evidence is None:
            evidence = {}
            event.evidence = evidence  # type: ignore[assignment]
        if not isinstance(evidence, dict):
            # Avoid crashing the pipeline if evidence is malformed
            return

        # Prefer tool_output; fall back to common alternative keys
        tool_output = evidence.get("tool_output")
        if tool_output is None:
            # Some producers may store the upstream response/body under different keys
            for k in ("response", "raw_response", "body", "output"):
                if k in evidence:
                    tool_output = evidence.get(k)
                    break

        # Only skip when truly absent (not just empty/falsey)
        if tool_output is None:
            return

        # Extract usage using existing extractor
        cost_usage, parse_error = UsageExtractor.extract(
            tool_output=tool_output,
            run_id=getattr(event, "run_id", None),
            step_id=getattr(event, "step_id", None),
            tool_name=getattr(event, "tool_name", None),
        )

        if not cost_usage:
            # Record parse error for debugging (only if meaningful and JSON-safe)
            if parse_error:
                evidence["usage_parse_error"] = str(parse_error)
            return

        # Prefer explicit prompt/completion if present, otherwise alias from input/output
        prompt_tokens = getattr(cost_usage, "prompt_tokens", None)
        completion_tokens = getattr(cost_usage, "completion_tokens", None)

        input_tokens = getattr(cost_usage, "input_tokens", None)
        output_tokens = getattr(cost_usage, "output_tokens", None)

        if prompt_tokens is None:
            prompt_tokens = input_tokens
        if completion_tokens is None:
            completion_tokens = output_tokens

        total_tokens = getattr(cost_usage, "total_tokens", None)
        if total_tokens is None:
            try:
                total_tokens = (int(prompt_tokens or 0) + int(completion_tokens or 0))
            except Exception:
                total_tokens = None

        # JSON-serializable coercions (avoid Decimal/numpy/etc.)
        cost_usd = getattr(cost_usage, "cost_usd", None)
        if cost_usd is not None:
            try:
                cost_usd = float(cost_usd)
            except Exception:
                # Last resort: stringify to avoid JSON writer crashes
                cost_usd = str(cost_usd)

        estimated = getattr(cost_usage, "estimated", None)
        if estimated is not None:
            try:
                estimated = bool(estimated)
            except Exception:
                estimated = True

        api_calls = getattr(cost_usage, "api_calls", None)
        if api_calls is not None:
            try:
                api_calls = int(api_calls)
            except Exception:
                api_calls = 1

        model = getattr(cost_usage, "model", None)
        provider = getattr(cost_usage, "provider", None)
        source = getattr(cost_usage, "source", None)

        # Standardized usage dict (keep both naming conventions for compatibility)
        evidence["usage"] = {
            # Generic / Anthropic-style
            "input_tokens": int(input_tokens) if isinstance(input_tokens, (int, float)) else input_tokens,
            "output_tokens": int(output_tokens) if isinstance(output_tokens, (int, float)) else output_tokens,
            # OpenAI-style aliases
            "prompt_tokens": int(prompt_tokens) if isinstance(prompt_tokens, (int, float)) else prompt_tokens,
            "completion_tokens": int(completion_tokens) if isinstance(completion_tokens, (int, float)) else completion_tokens,
            "total_tokens": int(total_tokens) if isinstance(total_tokens, (int, float)) else total_tokens,
            # Cost metadata
            "cost_usd": cost_usd,
            "estimated": estimated,
            "source": source,
            "model": model,
            "provider": provider,
            "api_calls": api_calls,
        }


__all__ = ["UsageEnricher"]
