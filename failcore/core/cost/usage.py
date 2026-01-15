# failcore/core/cost/usage.py
"""
Usage Extractor - Core Engine

Extract real usage information from tool return values
Supports multiple tool return formats (LLM provider, API responses, etc.)

Core features:
- Multi-path detection for nested usage structures
- Type normalization (safe_int/safe_float)
- Source tracking (provider_reported/gateway_reported/estimated)
- Parse error reporting (no silent failures)
- Extensible extractor registry

Extractors are in failcore/core/cost/extractors/ and auto-registered on import.

Architecture Note:
- This module provides the extraction logic
- Called by: executor stages (direct), egress enrichers (unified pipeline)
- See: failcore/core/egress/enrichers/usage.py for enricher integration
"""

from typing import Any, Optional, Dict, Tuple, Callable
from .models import CostUsage
from failcore.config.cost import (
    USAGE_CANDIDATE_PATHS,
    KNOWN_PROVIDER_REPORTED,
    STANDARD_TOKEN_FIELDS,
)

# New architecture imports (Phase C: Provider Metadata Registry)
from .registry import get_default_registry
from .pipeline import ExtractionPipeline
from .models import CostUsage

# Extractors are registered via cost/__init__.py to avoid circular imports


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int
    
    Handles:
    - None -> default
    - String numbers -> int
    - Decimal/float -> int
    - Invalid -> default
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        int value
    """
    if value is None:
        return default
    
    if isinstance(value, int):
        return value
    
    if isinstance(value, (float, str)):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    # Try to convert Decimal or other numeric types
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float
    
    Handles:
    - None -> default
    - String numbers -> float
    - Int -> float
    - Invalid -> default
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        float value
    """
    if value is None:
        return default
    
    if isinstance(value, float):
        return value
    
    if isinstance(value, (int, str)):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    # Try to convert Decimal or other numeric types
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


class UsageExtractor:
    """
    Extract usage information from tool return values
    
    Supports:
    1. Multi-path detection (nested structures)
    2. Type normalization (safe conversion)
    3. Source tracking (provider vs gateway)
    4. Parse error reporting
    5. Extensible extractor registry
    """
    
    # Extractor registry: tool_name or provider -> extractor function
    _extractors: Dict[str, Callable[[Any], Optional[Dict[str, Any]]]] = {}
    
    @classmethod
    def register(cls, name: str, extractor: Callable[[Any], Optional[Dict[str, Any]]]) -> None:
        """
        Register a custom extractor (deprecated - use ProviderRegistry instead)
        
        Args:
            name: Tool name or provider name (e.g., "openai", "anthropic", "llm_call")
            extractor: Function that takes tool_output and returns usage dict or None
        
        Deprecated:
            Use ProviderRegistry.register() with ProviderMetadata instead.
            This method is kept only for runtime custom extractors.
        """
        cls._extractors[name] = extractor
    
    @staticmethod
    def _detect_provider(tool_output: Any) -> Optional[str]:
        """
        Detect provider from tool output
        
        Args:
            tool_output: Tool return value
        
        Returns:
            Provider name if detected, None otherwise
        
        Detection strategies:
        1. Explicit provider field in dict
        2. Object class name heuristics (e.g., OpenAI response objects)
        3. Structure heuristics (field names)
        """
        # Strategy 1: Explicit provider field
        if isinstance(tool_output, dict):
            provider = tool_output.get("provider") or tool_output.get("model_provider")
            if provider:
                return str(provider).lower()
        
        # Strategy 2: Object class name heuristics
        if hasattr(tool_output, "__class__"):
            class_name = tool_output.__class__.__name__.lower()
            # OpenAI SDK classes
            if "openai" in class_name or "chatcompletion" in class_name:
                return "openai"
            # Anthropic SDK classes
            if "anthropic" in class_name or "message" in class_name:
                return "anthropic"
            # Google SDK classes
            if "google" in class_name or "gemini" in class_name:
                return "google"
        
        # Strategy 3: Structure heuristics (look for usage in common paths)
        if isinstance(tool_output, dict):
            # Check for OpenAI-style structure
            if "choices" in tool_output and isinstance(tool_output.get("choices"), list):
                return "openai"
            # Check for Anthropic-style structure
            if "content" in tool_output and "stop_reason" in tool_output:
                return "anthropic"
        
        return None
    
    @staticmethod
    def _extract_via_registry(
        tool_output: Any,
        provider_name: str,
        run_id: str,
        step_id: str,
        tool_name: str,
    ) -> Tuple[Optional[CostUsage], Optional[str]]:
        """
        Extract usage using Provider Metadata Registry (Phase C)
        
        Args:
            tool_output: Tool return value
            provider_name: Detected provider name
            run_id: Run ID
            step_id: Step ID
            tool_name: Tool name
        
        Returns:
            Tuple of (CostUsage, error_reason)
        """
        # Get provider metadata from registry
        registry = get_default_registry()
        metadata = registry.get(provider_name)
        
        if not metadata:
            # Provider not in registry, return None to fallback
            return None, f"provider_not_in_registry: {provider_name}"
        
        # Run extraction pipeline
        extracted_dict, error, path = ExtractionPipeline.extract(
            tool_output,
            metadata.extraction_rule,
        )
        
        if not extracted_dict:
            return None, error or "extraction_failed"
        
        # Optional: Run Pydantic validation if validator specified
        if metadata.validator:
            try:
                validated = metadata.validator(**extracted_dict)
                # Convert back to dict after validation
                extracted_dict = validated.model_dump()
            except Exception as e:
                # Validation failed, but continue (lenient mode)
                # In production, you might want to log this
                pass
        
        # Convert to CostUsage
        # Use provider/model from extracted dict if available, otherwise use metadata
        extracted_provider = extracted_dict.get("provider") or metadata.provider
        extracted_model = extracted_dict.get("model")
        
        # Determine source: use standard value, metadata details go in raw_usage
        source_value = "provider_reported" if not metadata.estimated else "estimated"
        
        cost_usage = CostUsage(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            input_tokens=extracted_dict.get("input_tokens", 0),
            output_tokens=extracted_dict.get("output_tokens", 0),
            total_tokens=extracted_dict.get("total_tokens", 0),
            cost_usd=extracted_dict.get("cost_usd") or 0.0,  # Ensure not None
            model=extracted_model,
            provider=extracted_provider,
            estimated=metadata.estimated,
            # Optional fields
            cache_creation_input_tokens=extracted_dict.get("cache_creation_input_tokens"),
            cache_read_input_tokens=extracted_dict.get("cache_read_input_tokens"),
            reasoning_tokens=extracted_dict.get("reasoning_tokens"),
            audio_tokens=extracted_dict.get("audio_tokens"),
            cached_tokens=extracted_dict.get("cached_tokens"),
            # Use standard source value
            source=source_value,
            # Store extraction metadata in raw_usage for observability
            raw_usage={
                **(extracted_dict or {}),
                "_extraction_metadata": {
                    "provider_metadata": metadata.full_name,
                    "extraction_path": path,
                }
            },
        )
        
        return cost_usage, None
    
    @classmethod
    def _find_usage(cls, tool_output: Any) -> Tuple[Optional[Any], Optional[str]]:
        """
        Find usage data in tool output using multiple candidate paths
        
        Args:
            tool_output: Tool return value
        
        Returns:
            Tuple of (usage_data, source_hint)
            - usage_data: Found usage dict/object, or None
            - source_hint: Path where usage was found (for debugging)
        """
        # Try registered extractors first
        # (Check by tool_name if available, or by provider)
        if isinstance(tool_output, dict):
            provider = tool_output.get("provider")
            tool_name = tool_output.get("tool_name")
            
            if provider and provider in cls._extractors:
                result = cls._extractors[provider](tool_output)
                if result:
                    return result, f"registered_extractor:{provider}"
            
            if tool_name and tool_name in cls._extractors:
                result = cls._extractors[tool_name](tool_output)
                if result:
                    return result, f"registered_extractor:{tool_name}"
        
        # Try dict paths
        if isinstance(tool_output, dict):
            for path in USAGE_CANDIDATE_PATHS:
                if "." in path or "[" in path:
                    # Handle nested paths like "result.usage" or "choices[0].message.usage"
                    parts = path.split(".")
                    current = tool_output
                    found = True
                    for part in parts:
                        if "[" in part:
                            # Handle array access like "choices[0]"
                            key, index = part.split("[")
                            index = int(index.rstrip("]"))
                            if isinstance(current, dict) and key in current:
                                arr = current[key]
                                if isinstance(arr, (list, tuple)) and len(arr) > index:
                                    current = arr[index]
                                else:
                                    found = False
                                    break
                            else:
                                found = False
                                break
                        else:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                found = False
                                break
                    
                    if found and current is not None:
                        return current, path
                else:
                    # Simple key lookup
                    if path in tool_output:
                        return tool_output[path], path
        
        # Try object attributes
        if not isinstance(tool_output, dict):
            for path in USAGE_CANDIDATE_PATHS:
                if "." in path:
                    # Handle nested attributes like "response.usage"
                    parts = path.split(".")
                    current = tool_output
                    found = True
                    for part in parts:
                        if hasattr(current, part):
                            current = getattr(current, part, None)
                            if current is None:
                                found = False
                                break
                        else:
                            found = False
                            break
                    
                    if found and current is not None:
                        return current, path
                else:
                    # Simple attribute lookup
                    if hasattr(tool_output, path):
                        attr = getattr(tool_output, path, None)
                        if attr is not None:
                            return attr, path
        
        return None, None
    
    @staticmethod
    def extract(
            tool_output: Any,
            run_id: str,
            step_id: str,
            tool_name: str,
    ) -> Tuple[Optional[CostUsage], Optional[str]]:
        """
        Try to extract usage from tool output
        
        Strategy (Phase C: Provider Metadata Registry):
        1. Try new registry-based extraction (provider metadata)
        2. Fallback to legacy extractor registry
        3. Fallback to generic multi-path detection
        
        Args:
            tool_output: Tool return value
            run_id: Run ID
            step_id: Step ID
            tool_name: Tool name
        
        Returns:
            Tuple of (CostUsage, parse_error_reason)
            - CostUsage if extracted successfully, None otherwise
            - parse_error_reason: Reason if extraction failed (for trace logging)
        """
        # Strategy 1: Try new Provider Metadata Registry (Phase C)
        # First check explicit provider field in dict (top-level or in usage)
        provider_name = None
        if isinstance(tool_output, dict):
            provider_name = tool_output.get("provider") or tool_output.get("model_provider")
            # Also check inside usage dict
            if not provider_name and "usage" in tool_output:
                usage_dict = tool_output.get("usage")
                if isinstance(usage_dict, dict):
                    provider_name = usage_dict.get("provider") or usage_dict.get("model_provider")
            if provider_name:
                provider_name = str(provider_name).lower()
        
        # If not found, try detection heuristics
        if not provider_name:
            provider_name = UsageExtractor._detect_provider(tool_output)
        
        if provider_name:
            result, error = UsageExtractor._extract_via_registry(
                tool_output,
                provider_name,
                run_id,
                step_id,
                tool_name,
            )
            if result:
                return result, error
        
        # Strategy 2: Fallback to runtime custom extractors (if registered)
        if isinstance(tool_output, dict):
            provider = tool_output.get("provider")
            if provider and provider in UsageExtractor._extractors:
                usage_data = UsageExtractor._extractors[provider](tool_output)
                if usage_data:
                    return UsageExtractor._parse_usage_data(
                        usage_data,
                        run_id,
                        step_id,
                        tool_name,
                        source_hint=f"custom_extractor:{provider}",
                    )
            
            if tool_name and tool_name in UsageExtractor._extractors:
                usage_data = UsageExtractor._extractors[tool_name](tool_output)
                if usage_data:
                    return UsageExtractor._parse_usage_data(
                        usage_data,
                        run_id,
                        step_id,
                        tool_name,
                        source_hint=f"custom_extractor:{tool_name}",
                    )
        
        # Strategy 3: Fallback to generic provider (last resort)
        # Try registry generic fallback first
        registry = get_default_registry()
        generic_metadata = registry.get("generic")
        if generic_metadata:
            extracted_dict, error, path = ExtractionPipeline.extract(
                tool_output,
                generic_metadata.extraction_rule,
            )
            if extracted_dict:
                # Determine estimated flag: if has standard token fields, mark as provider-reported
                has_standard_fields = (
                    extracted_dict.get("input_tokens", 0) > 0 or
                    extracted_dict.get("output_tokens", 0) > 0 or
                    extracted_dict.get("prompt_tokens") is not None or
                    extracted_dict.get("completion_tokens") is not None
                )
                # If has standard token fields, it's likely provider-reported (not estimated)
                is_estimated = not has_standard_fields
                source = "provider_reported" if not is_estimated else "gateway_reported"
                
                # Convert to CostUsage
                cost_usage = CostUsage(
                    run_id=run_id,
                    step_id=step_id,
                    tool_name=tool_name,
                    input_tokens=extracted_dict.get("input_tokens", 0),
                    output_tokens=extracted_dict.get("output_tokens", 0),
                    total_tokens=extracted_dict.get("total_tokens", 0),
                    cost_usd=extracted_dict.get("cost_usd") or 0.0,  # Ensure not None
                    model=extracted_dict.get("model"),
                    provider=extracted_dict.get("provider"),
                    estimated=is_estimated,
                    source=source,
                    raw_usage=extracted_dict,
                    api_calls=1,
                )
                return cost_usage, None
        
        # Final fallback: legacy multi-path detection
        usage_data, source_hint = UsageExtractor._find_usage(tool_output)
        
        if not usage_data:
            return None, "usage_not_found"
        
        # Convert object to dict if needed
        if not isinstance(usage_data, dict):
            usage_dict = {}
            if hasattr(usage_data, "__dict__"):
                usage_dict = vars(usage_data)
            
            # If vars() returns empty, try extracting attributes manually
            if not usage_dict:
                for attr in ['prompt_tokens', 'completion_tokens', 'total_tokens',
                             'input_tokens', 'output_tokens', 'cost_usd', 'model', 'provider',
                             'cache_creation_input_tokens', 'cache_read_input_tokens',
                             'reasoning_tokens', 'input_tokens_details', 'output_tokens_details']:
                    if hasattr(usage_data, attr):
                        usage_dict[attr] = getattr(usage_data, attr)
            
            if usage_dict:
                usage_data = usage_dict
            else:
                return None, f"usage_found_but_not_dict_or_object (path: {source_hint})"
        
        # Before parsing, check if we should try generic registry one more time
        # (in case _find_usage found the usage dict but we didn't try generic yet)
        if isinstance(usage_data, dict) and not usage_data.get("provider"):
            registry = get_default_registry()
            generic_metadata = registry.get("generic")
            if generic_metadata:
                # Try extracting from the usage_data dict directly
                extracted_dict, error, path = ExtractionPipeline.extract(
                    {"usage": usage_data},  # Wrap in a dict with "usage" key
                    generic_metadata.extraction_rule,
                )
                if extracted_dict and (extracted_dict.get("input_tokens", 0) > 0 or extracted_dict.get("output_tokens", 0) > 0):
                    # Has standard token fields - mark as provider-reported
                    has_standard_fields = (
                        extracted_dict.get("input_tokens", 0) > 0 or
                        extracted_dict.get("output_tokens", 0) > 0
                    )
                    is_estimated = not has_standard_fields
                    source = "provider_reported" if not is_estimated else "gateway_reported"
                    
                    cost_usage = CostUsage(
                        run_id=run_id,
                        step_id=step_id,
                        tool_name=tool_name,
                        input_tokens=extracted_dict.get("input_tokens", 0),
                        output_tokens=extracted_dict.get("output_tokens", 0),
                        total_tokens=extracted_dict.get("total_tokens", 0),
                        cost_usd=extracted_dict.get("cost_usd") or 0.0,  # Ensure not None
                        model=extracted_dict.get("model"),
                        provider=extracted_dict.get("provider"),
                        estimated=is_estimated,
                        source=source,
                        raw_usage=extracted_dict,
                        api_calls=1,
                    )
                    return cost_usage, None
        
        # Parse usage data (with type normalization and source detection)
        return UsageExtractor._parse_usage_data(
            usage_data,
            run_id,
            step_id,
            tool_name,
            source_hint=source_hint,
        )
    
    @staticmethod
    def _parse_usage_data(
            usage_data: Dict[str, Any],
            run_id: str,
            step_id: str,
            tool_name: str,
            source_hint: Optional[str] = None,
    ) -> Tuple[Optional[CostUsage], Optional[str]]:
        """
        Parse usage data to CostUsage with type normalization
        
        Supported formats:
        - OpenAI: {prompt_tokens, completion_tokens, total_tokens}
        - Anthropic: {input_tokens, output_tokens}
        - Generic: {input_tokens, output_tokens, total_tokens, cost_usd}
        
        Args:
            usage_data: Usage dict
            run_id: Run ID
            step_id: Step ID
            tool_name: Tool name
            source_hint: Hint about where usage was found
        
        Returns:
            Tuple of (CostUsage, parse_error_reason)
        """
        if not isinstance(usage_data, dict):
            return None, "usage_data_not_dict"
        
        # Store raw usage for audit/debugging
        raw_usage = usage_data.copy()
        
        # Extract token counts with type normalization
        input_tokens = safe_int(
            usage_data.get("input_tokens") or
            usage_data.get("prompt_tokens") or
            0
        )
        
        output_tokens = safe_int(
            usage_data.get("output_tokens") or
            usage_data.get("completion_tokens") or
            0
        )
        
        # Handle extended token types (reasoning, cache, etc.)
        reasoning_tokens = safe_int(usage_data.get("reasoning_tokens", 0))
        cache_creation_tokens = safe_int(usage_data.get("cache_creation_input_tokens", 0))
        cache_read_tokens = safe_int(usage_data.get("cache_read_input_tokens", 0))
        
        # Calculate total tokens (include extended types if available)
        total_tokens = safe_int(
            usage_data.get("total_tokens") or
            (input_tokens + output_tokens + reasoning_tokens + cache_creation_tokens + cache_read_tokens)
        )
        
        # Extract cost with type normalization (ensure not None)
        cost_usd = safe_float(usage_data.get("cost_usd", 0.0)) or 0.0
        
        # Extract model/provider info
        model = usage_data.get("model")
        provider = usage_data.get("provider")
        
        # Determine source and estimated flag
        # Check registry first (most reliable)
        estimated = True  # Default to estimated
        source = "unknown"
        
        if provider:
            provider_lower = str(provider).lower()
            # Check registry
            registry = get_default_registry()
            metadata = registry.get(provider_lower)
            if metadata:
                estimated = metadata.estimated
                source = "provider_reported" if not estimated else "gateway_reported"
            elif provider_lower in KNOWN_PROVIDER_REPORTED:
                # Legacy known providers
                estimated = False
                source = "provider_reported"
            else:
                # Unknown provider, check if has standard token fields
                has_standard_fields = (
                    (usage_data.get("prompt_tokens") is not None and usage_data.get("completion_tokens") is not None) or
                    (usage_data.get("input_tokens") is not None and usage_data.get("output_tokens") is not None)
                )
                if has_standard_fields:
                    # Unknown provider but has standard format - likely provider-reported
                    estimated = False
                    source = "provider_reported"
                else:
                    source = "gateway_reported"
                    estimated = True
        else:
            # No provider, check if has standard token fields
            has_standard_fields = (
                (usage_data.get("prompt_tokens") is not None and usage_data.get("completion_tokens") is not None) or
                (usage_data.get("input_tokens") is not None and usage_data.get("output_tokens") is not None)
            )
            if has_standard_fields:
                # Has standard token fields but no provider - assume provider-reported (not estimated)
                estimated = False
                source = "provider_reported"
            elif usage_data.get("cost_usd") is not None or usage_data.get("total_tokens") is not None:
                # Has usage data but no provider info and no standard fields
                source = "gateway_reported"
                estimated = True
            else:
                source = "unknown"
                estimated = True
        
        # Validate: if all tokens are 0 and cost is 0, might be invalid
        if input_tokens == 0 and output_tokens == 0 and total_tokens == 0 and cost_usd == 0.0:
            # Check if this is actually empty or just normalized to 0
            has_any_token_field = any(k in usage_data for k in STANDARD_TOKEN_FIELDS)
            if not has_any_token_field:
                return None, "usage_data_empty_or_invalid"
        
        try:
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
                estimated=estimated,
                source=source,
                raw_usage=raw_usage,
                api_calls=1,
            ), None
        except ValueError as e:
            # CostUsage validation failed
            return None, f"cost_usage_validation_failed: {str(e)}"


__all__ = ["UsageExtractor", "safe_int", "safe_float"]
