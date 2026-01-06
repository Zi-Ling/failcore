# failcore/core/replay/drift/rules.py
"""
Drift Detection Rules - deterministic heuristics for parameter drift

Detects drift using three rule types:
1. Value changed: Field value differs from baseline
2. Magnitude changed: Numeric/length change exceeds threshold
3. Domain changed: Path/host/pattern escapes baseline domain
"""

from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse

from .types import DriftChange
from .config import DriftConfig, get_default_config


def detect_drift(
    baseline_params: Dict[str, Any],
    current_params: Dict[str, Any],
    tool_name: str,
    config: Optional[DriftConfig] = None,
) -> List[DriftChange]:
    """
    Detect drift between baseline and current parameters
    
    Applies three rule types:
    1. Value changed: Any field difference
    2. Magnitude changed: Numeric/length change > threshold
    3. Domain changed: Path/host/pattern domain escape
    
    Args:
        baseline_params: Normalized baseline parameters
        current_params: Normalized current parameters
        tool_name: Tool name (for tool-specific rules)
        config: Optional drift configuration (uses default if None)
    
    Returns:
        List of DriftChange objects detected
    """
    if config is None:
        config = get_default_config()
    
    changes = []
    ignore_fields = config.get_ignore_fields(tool_name)
    
    # Check all fields in current params
    for field_path, current_value in _flatten_dict(current_params, ignore_fields):
        baseline_value = _get_nested_value(baseline_params, field_path)
        
        # Skip if field is ignored
        field_name = field_path.split(".")[-1]
        if field_name in ignore_fields:
            continue
        
        # Detect change
        change = _detect_field_drift(
            field_path,
            baseline_value,
            current_value,
            tool_name,
            config,
        )
        
        if change:
            changes.append(change)
    
    # Also check for fields removed from baseline
    for field_path, baseline_value in _flatten_dict(baseline_params, ignore_fields):
        field_name = field_path.split(".")[-1]
        if field_name in ignore_fields:
            continue
        
        current_value = _get_nested_value(current_params, field_path)
        if current_value is None and baseline_value is not None:
            # Field was removed
            change = DriftChange(
                field_path=field_path,
                baseline_value=baseline_value,
                current_value=None,
                change_type="value_changed",
                severity="medium",
                reason=f"Field removed: {field_path}",
            )
            changes.append(change)
    
    return changes


def _detect_field_drift(
    field_path: str,
    baseline_value: Any,
    current_value: Any,
    tool_name: str,
    config: DriftConfig,
) -> Optional[DriftChange]:
    """
    Detect drift for a single field
    
    Args:
        field_path: Field path (e.g., "path", "options.timeout")
        baseline_value: Baseline value
        current_value: Current value
        tool_name: Tool name
        config: Drift configuration
    
    Returns:
        DriftChange if drift detected, None otherwise
    """
    # No baseline value means new field (value_changed)
    if baseline_value is None:
        if current_value is not None:
            return DriftChange(
                field_path=field_path,
                baseline_value=None,
                current_value=current_value,
                change_type="value_changed",
                severity="low",
                reason=f"New field added: {field_path}",
            )
        return None
    
    # No current value means field removed (handled in detect_drift)
    if current_value is None:
        return None
    
    # Check for exact value change
    if baseline_value != current_value:
        # Try domain changed first (highest severity)
        domain_change = _check_domain_changed(
            field_path,
            baseline_value,
            current_value,
            config,
        )
        if domain_change:
            return domain_change
        
        # Try magnitude changed (medium severity)
        magnitude_change = _check_magnitude_changed(
            field_path,
            baseline_value,
            current_value,
            config,
        )
        if magnitude_change:
            return magnitude_change
        
        # Default to value changed (low severity)
        return DriftChange(
            field_path=field_path,
            baseline_value=baseline_value,
            current_value=current_value,
            change_type="value_changed",
            severity="low",
            reason=f"Value changed: {field_path}",
        )
    
    return None


def _check_domain_changed(
    field_path: str,
    baseline_value: Any,
    current_value: Any,
    config: DriftConfig,
) -> Optional[DriftChange]:
    """
    Check if domain changed (path/host/pattern escaped baseline domain)
    
    Args:
        field_path: Field path
        baseline_value: Baseline value
        current_value: Current value
        config: Drift configuration
    
    Returns:
        DriftChange if domain changed, None otherwise
    """
    field_name = field_path.split(".")[-1].lower()
    
    # Check path-like fields
    if field_name in ("path", "file", "filepath", "directory", "dir", "output", "input"):
        if isinstance(baseline_value, str) and isinstance(current_value, str):
            baseline_domain = _extract_path_domain(baseline_value)
            current_domain = _extract_path_domain(current_value)
            
            if baseline_domain and current_domain and baseline_domain != current_domain:
                return DriftChange(
                    field_path=field_path,
                    baseline_value=baseline_value,
                    current_value=current_value,
                    change_type="domain_changed",
                    severity="high",
                    reason=f"Path escaped baseline domain: {baseline_domain} -> {current_domain}",
                )
    
    # Check URL/host fields
    if field_name in ("url", "host", "hostname", "endpoint", "api", "base_url"):
        if isinstance(baseline_value, str) and isinstance(current_value, str):
            baseline_domain = _extract_url_domain(baseline_value)
            current_domain = _extract_url_domain(current_value)
            
            if baseline_domain and current_domain and baseline_domain != current_domain:
                return DriftChange(
                    field_path=field_path,
                    baseline_value=baseline_value,
                    current_value=current_value,
                    change_type="domain_changed",
                    severity="high",
                    reason=f"Host escaped baseline domain: {baseline_domain} -> {current_domain}",
                )
    
    return None


def _check_magnitude_changed(
    field_path: str,
    baseline_value: Any,
    current_value: Any,
    config: DriftConfig,
) -> Optional[DriftChange]:
    """
    Check if magnitude changed (numeric/length change > threshold)
    
    Args:
        field_path: Field path
        baseline_value: Baseline value
        current_value: Current value
        config: Drift configuration
    
    Returns:
        DriftChange if magnitude changed, None otherwise
    """
    # Check numeric values
    if isinstance(baseline_value, (int, float)) and isinstance(current_value, (int, float)):
        if baseline_value == 0:
            return None  # Can't compute ratio
        
        ratio = abs(current_value / baseline_value)
        
        if ratio >= config.magnitude_threshold_high:
            return DriftChange(
                field_path=field_path,
                baseline_value=baseline_value,
                current_value=current_value,
                change_type="magnitude_changed",
                severity="high",
                reason=f"Magnitude change {ratio:.1f}x (>= {config.magnitude_threshold_high}x)",
            )
        elif ratio >= config.magnitude_threshold_medium:
            return DriftChange(
                field_path=field_path,
                baseline_value=baseline_value,
                current_value=current_value,
                change_type="magnitude_changed",
                severity="medium",
                reason=f"Magnitude change {ratio:.1f}x (>= {config.magnitude_threshold_medium}x)",
            )
    
    # Check string length
    if isinstance(baseline_value, str) and isinstance(current_value, str):
        baseline_len = len(baseline_value)
        current_len = len(current_value)
        
        if baseline_len == 0:
            return None  # Can't compute ratio
        
        ratio = current_len / baseline_len
        
        if ratio >= config.magnitude_threshold_high:
            return DriftChange(
                field_path=field_path,
                baseline_value=baseline_value,
                current_value=current_value,
                change_type="magnitude_changed",
                severity="high",
                reason=f"Length change {ratio:.1f}x (>= {config.magnitude_threshold_high}x)",
            )
        elif ratio >= config.magnitude_threshold_medium:
            return DriftChange(
                field_path=field_path,
                baseline_value=baseline_value,
                current_value=current_value,
                change_type="magnitude_changed",
                severity="medium",
                reason=f"Length change {ratio:.1f}x (>= {config.magnitude_threshold_medium}x)",
            )
    
    # Check list/array length
    if isinstance(baseline_value, list) and isinstance(current_value, list):
        baseline_len = len(baseline_value)
        current_len = len(current_value)
        
        if baseline_len == 0:
            return None  # Can't compute ratio
        
        ratio = current_len / baseline_len
        
        if ratio >= config.magnitude_threshold_high:
            return DriftChange(
                field_path=field_path,
                baseline_value=baseline_value,
                current_value=current_value,
                change_type="magnitude_changed",
                severity="high",
                reason=f"Array length change {ratio:.1f}x (>= {config.magnitude_threshold_high}x)",
            )
        elif ratio >= config.magnitude_threshold_medium:
            return DriftChange(
                field_path=field_path,
                baseline_value=baseline_value,
                current_value=current_value,
                change_type="magnitude_changed",
                severity="medium",
                reason=f"Array length change {ratio:.1f}x (>= {config.magnitude_threshold_medium}x)",
            )
    
    return None


def _extract_path_domain(path: str) -> Optional[str]:
    """
    Extract domain (base directory) from a path
    
    Args:
        path: File path
    
    Returns:
        Domain (base directory) or None if not applicable
    """
    if not path:
        return None
    
    # Normalize path separators
    normalized = path.replace("\\", "/")
    
    # Extract first component (domain)
    parts = normalized.split("/")
    
    # Skip empty parts (leading /)
    parts = [p for p in parts if p]
    
    if not parts:
        return None
    
    # Return first 1-2 components as domain
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _extract_url_domain(url: str) -> Optional[str]:
    """
    Extract domain from a URL or hostname
    
    Args:
        url: URL string or hostname (e.g., "https://api.example.com" or "api.example.com")
    
    Returns:
        Domain (hostname) or None if not applicable
    """
    if not url:
        return None
    
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            # Extract hostname (without port)
            hostname = parsed.netloc.split(":")[0]
            return hostname
        # If no scheme, try parsing with a default scheme
        if not parsed.scheme and parsed.path:
            # Check if it looks like a hostname (contains dots, no slashes)
            if "." in parsed.path and "/" not in parsed.path:
                # Treat as hostname directly
                hostname = parsed.path.split(":")[0]  # Remove port if present
                return hostname
            # Try with http:// prefix
            parsed_with_scheme = urlparse(f"http://{url}")
            if parsed_with_scheme.netloc:
                hostname = parsed_with_scheme.netloc.split(":")[0]
                return hostname
    except Exception:
        pass
    
    return None


def _flatten_dict(d: Dict[str, Any], ignore_fields: Set[str], prefix: str = "") -> List[tuple]:
    """
    Flatten nested dictionary to list of (path, value) tuples
    
    Args:
        d: Dictionary to flatten
        ignore_fields: Fields to ignore
        prefix: Prefix for nested paths
    
    Returns:
        List of (field_path, value) tuples
    """
    result = []
    
    for key, value in d.items():
        if key in ignore_fields:
            continue
        
        field_path = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            # Recursively flatten nested dicts
            result.extend(_flatten_dict(value, ignore_fields, field_path))
        else:
            result.append((field_path, value))
    
    return result


def _get_nested_value(d: Dict[str, Any], path: str) -> Any:
    """
    Get nested value from dictionary by path
    
    Args:
        d: Dictionary
        path: Field path (e.g., "options.timeout")
    
    Returns:
        Value at path or None if not found
    """
    parts = path.split(".")
    current = d
    
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    
    return current


__all__ = ["detect_drift"]
