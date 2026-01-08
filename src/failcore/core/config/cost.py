# failcore/core/config/cost.py
"""
Cost extraction configuration

Centralized configuration for cost/token extraction, including:
- Usage candidate paths
- Known provider lists
- Conflict detection thresholds
- Extractor registry settings
"""

from typing import List

# Candidate paths for finding usage in nested structures
USAGE_CANDIDATE_PATHS: List[str] = [
    "usage",                    # Top-level
    "result.usage",             # Wrapped in result
    "response.usage",           # Wrapped in response
    "meta.usage",               # In metadata
    "data.usage",               # In data field
    "payload.usage",            # In payload
    "raw.usage",                # In raw field
    "_usage",                   # Private attribute
    "choices[0].message.usage", # OpenAI-style nested
    "raw_response.usage",       # Raw response wrapper
]

# Known providers that report usage in standard format
# Used to determine if usage is "provider_reported" (estimated=False)
KNOWN_PROVIDER_REPORTED: List[str] = [
    "openai",
    "anthropic",
    "google",
    "cohere",
    "mistral",
]

# Conflict detection threshold (ratio of difference to max value)
# If cost difference > threshold, record COST_USAGE_CONFLICT event
COST_CONFLICT_THRESHOLD: float = 0.3  # 30%

# Token field names that indicate standard provider format
STANDARD_TOKEN_FIELDS: List[str] = [
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
]

__all__ = [
    "USAGE_CANDIDATE_PATHS",
    "KNOWN_PROVIDER_REPORTED",
    "COST_CONFLICT_THRESHOLD",
    "STANDARD_TOKEN_FIELDS",
]
