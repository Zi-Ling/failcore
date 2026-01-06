# failcore/core/replay/drift/normalize.py
"""
Parameter Normalization - normalizes parameters for drift comparison

Normalizes parameters to remove noise and enable meaningful comparison:
- String trimming
- Path separator normalization
- Type coercion
- List sorting (for unordered sets)
- Dynamic field removal
"""

from typing import Dict, Any, List, Optional, Set
import json

from .config import DriftConfig, get_default_config


def normalize_params(
    params: Dict[str, Any],
    tool_name: str,
    config: Optional[DriftConfig] = None,
) -> Dict[str, Any]:
    """
    Normalize parameters for drift comparison
    
    Applies normalization rules:
    1. Remove ignored fields (dynamic fields)
    2. Normalize strings (trim whitespace)
    3. Normalize paths (unify separators)
    4. Coerce types (convert compatible types)
    5. Sort lists (for unordered set fields)
    
    Args:
        params: Parameters dictionary
        tool_name: Tool name (for tool-specific rules)
        config: Optional drift configuration (uses default if None)
    
    Returns:
        Normalized parameters dictionary
    """
    if config is None:
        config = get_default_config()
    
    if not isinstance(params, dict):
        return {}
    
    normalized = {}
    ignore_fields = config.get_ignore_fields(tool_name)
    
    for key, value in params.items():
        # Skip ignored fields
        if key in ignore_fields:
            continue
        
        # Normalize value
        normalized_value = _normalize_value(value, key, tool_name, config)
        
        # Only include non-None values (or keep None if explicitly set)
        normalized[key] = normalized_value
    
    return normalized


def _normalize_value(
    value: Any,
    field_name: str,
    tool_name: str,
    config: DriftConfig,
) -> Any:
    """
    Normalize a single value
    
    Args:
        value: Value to normalize
        field_name: Field name (for field-specific rules)
        tool_name: Tool name (for tool-specific rules)
        config: Drift configuration
    
    Returns:
        Normalized value
    """
    if value is None:
        return None
    
    # String normalization
    if isinstance(value, str):
        normalized = value
        
        # Trim whitespace
        if config.normalize_whitespace:
            normalized = normalized.strip()
        
        # Normalize paths (Windows \ to Unix /)
        if config.normalize_paths and _looks_like_path(normalized):
            normalized = normalized.replace("\\", config.path_separator)
            # Normalize multiple separators
            while f"{config.path_separator}{config.path_separator}" in normalized:
                normalized = normalized.replace(
                    f"{config.path_separator}{config.path_separator}",
                    config.path_separator
                )
        
        # Convert empty string to None (optional, but helps with comparison)
        if normalized == "":
            return None
        
        return normalized
    
    # List normalization
    if isinstance(value, list):
        normalized_list = []
        
        for item in value:
            normalized_item = _normalize_value(item, field_name, tool_name, config)
            normalized_list.append(normalized_item)
        
        # Sort if this is an unordered set field
        if config.is_unordered_set_field(field_name):
            try:
                normalized_list.sort(key=_sort_key)
            except (TypeError, ValueError):
                # If sorting fails (mixed types), keep original order
                pass
        
        return normalized_list
    
    # Dictionary normalization (recursive)
    if isinstance(value, dict):
        return normalize_params(value, tool_name, config)
    
    # Type coercion (convert compatible types)
    if isinstance(value, (int, float)):
        # Normalize numeric types
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    
    # Boolean normalization
    if isinstance(value, bool):
        return value
    
    # Default: return as-is
    return value


def _looks_like_path(value: str) -> bool:
    """
    Heuristic to detect if a string looks like a file path
    
    Args:
        value: String value
    
    Returns:
        True if string looks like a path
    """
    if not value:
        return False
    
    # Check for path-like patterns
    path_indicators = ["/", "\\", ".", "..", "~"]
    if any(indicator in value for indicator in path_indicators):
        # Exclude URLs and other non-path patterns
        if not value.startswith(("http://", "https://", "ftp://", "file://")):
            return True
    
    return False


def _sort_key(value: Any) -> Any:
    """
    Generate sort key for a value
    
    Args:
        value: Value to generate sort key for
    
    Returns:
        Sort key
    """
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, dict):
        # Sort dicts by JSON string representation
        return json.dumps(value, sort_keys=True)
    if isinstance(value, list):
        # Sort lists by first element or length
        if value:
            return (_sort_key(value[0]), len(value))
        return (None, 0)
    return str(value)


__all__ = ["normalize_params"]
