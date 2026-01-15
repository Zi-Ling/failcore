# failcore/core/replay/drift/baseline.py
"""
Baseline Generation - builds parameter baselines for drift detection

Supports multiple baseline strategies:
1. first_occurrence: Use first occurrence (simple, but vulnerable to outliers)
2. median: Use median value (robust to outliers)
3. percentile: Use percentile value (configurable robustness)
4. segmented: Build baselines per segment (auto-segment by inflection points or stages)
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import statistics

from .types import ParamSnapshot
from .normalize import normalize_params
from .config import DriftConfig, get_default_config, BaselineStrategy
from .inflection import InflectionPoint


def build_baseline(
    snapshots: List[ParamSnapshot],
    config: Optional[DriftConfig] = None,
    inflection_points: Optional[List[InflectionPoint]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build baseline from parameter snapshots
    
    Supports multiple strategies:
    - first_occurrence: First occurrence (default)
    - median: Median value (robust)
    - percentile: Percentile value (configurable)
    - segmented: Per-segment baselines
    
    Args:
        snapshots: List of parameter snapshots (ordered by seq)
        config: Optional drift configuration (uses default if None)
        inflection_points: Optional inflection points for segmented baseline
    
    Returns:
        Dictionary mapping tool_name -> normalized baseline parameters
        Also includes baseline_strategy and baseline_window in metadata
    """
    if config is None:
        config = get_default_config()
    
    # Get baseline strategy from config
    strategy = getattr(config, 'baseline_strategy', BaselineStrategy.FIRST_OCCURRENCE)
    if isinstance(strategy, str):
        strategy = BaselineStrategy(strategy)
    
    baseline: Dict[str, Dict[str, Any]] = {}
    
    # Group snapshots by tool
    tool_snapshots: Dict[str, List[ParamSnapshot]] = {}
    for snapshot in snapshots:
        tool_name = snapshot.tool_name
        if tool_name not in tool_snapshots:
            tool_snapshots[tool_name] = []
        tool_snapshots[tool_name].append(snapshot)
    
    # Build baseline for each tool
    for tool_name, tool_snaps in tool_snapshots.items():
        if strategy == BaselineStrategy.SEGMENTED:
            baseline[tool_name] = _build_segmented_baseline(
                tool_snaps, config, inflection_points
            )
        else:
            baseline[tool_name] = _build_single_baseline(
                tool_snaps, config, strategy
            )
    
    return baseline


def _build_single_baseline(
    snapshots: List[ParamSnapshot],
    config: DriftConfig,
    strategy: BaselineStrategy,
) -> Dict[str, Any]:
    """
    Build single baseline using specified strategy
    
    Args:
        snapshots: Snapshots for one tool
        config: Drift configuration
        strategy: Baseline strategy
        
    Returns:
        Baseline parameters with metadata
    """
    if not snapshots:
        return {}
    
    tool_name = snapshots[0].tool_name
    
    # Normalize all snapshots
    normalized_snapshots = []
    for snapshot in snapshots:
        normalized = normalize_params(
            snapshot.params,
            tool_name,
            config,
        )
        normalized_snapshots.append(normalized)
    
    # Build baseline based on strategy
    if strategy == BaselineStrategy.FIRST_OCCURRENCE:
        baseline_params = normalized_snapshots[0]
        baseline_window = (snapshots[0].seq, snapshots[0].seq)
        
    elif strategy == BaselineStrategy.MEDIAN:
        baseline_params = _compute_median_baseline(normalized_snapshots)
        baseline_window = (snapshots[0].seq, snapshots[-1].seq)
        
    elif strategy == BaselineStrategy.PERCENTILE:
        percentile = getattr(config, 'baseline_percentile', 50.0)
        baseline_params = _compute_percentile_baseline(normalized_snapshots, percentile)
        baseline_window = (snapshots[0].seq, snapshots[-1].seq)
        
    else:
        # Fallback to first occurrence
        baseline_params = normalized_snapshots[0]
        baseline_window = (snapshots[0].seq, snapshots[0].seq)
    
    # Add metadata
    baseline_params["_baseline_metadata"] = {
        "strategy": strategy.value,
        "window": baseline_window,
        "snapshot_count": len(snapshots),
    }
    
    return baseline_params


def _build_segmented_baseline(
    snapshots: List[ParamSnapshot],
    config: DriftConfig,
    inflection_points: Optional[List[InflectionPoint]],
) -> Dict[str, Any]:
    """
    Build segmented baseline (per-segment baselines)
    
    Segments are defined by inflection points or fixed window size.
    
    Args:
        snapshots: Snapshots for one tool
        config: Drift configuration
        inflection_points: Optional inflection points for segmentation
        
    Returns:
        Segmented baseline with metadata
    """
    if not snapshots:
        return {}
    
    tool_name = snapshots[0].tool_name
    
    # Determine segments
    segments = _determine_segments(snapshots, inflection_points, config)
    
    # Build baseline per segment
    segment_baselines = {}
    for segment_id, (start_seq, end_seq) in enumerate(segments):
        segment_snapshots = [
            s for s in snapshots
            if start_seq <= s.seq <= end_seq
        ]
        
        if not segment_snapshots:
            continue
        
        # Use median for each segment (robust within segment)
        normalized_snapshots = [
            normalize_params(s.params, tool_name, config)
            for s in segment_snapshots
        ]
        
        segment_baseline = _compute_median_baseline(normalized_snapshots)
        segment_baselines[f"segment_{segment_id}"] = {
            "baseline": segment_baseline,
            "window": (start_seq, end_seq),
            "snapshot_count": len(segment_snapshots),
        }
    
    # Return segmented baseline structure
    return {
        "_baseline_metadata": {
            "strategy": BaselineStrategy.SEGMENTED.value,
            "segments": segment_baselines,
            "total_segments": len(segments),
        },
        # Use first segment as primary baseline for comparison
        **segment_baselines.get("segment_0", {}).get("baseline", {}),
    }


def _determine_segments(
    snapshots: List[ParamSnapshot],
    inflection_points: Optional[List[InflectionPoint]],
    config: DriftConfig,
) -> List[Tuple[int, int]]:
    """
    Determine segments for segmented baseline
    
    Args:
        snapshots: Snapshots for one tool
        inflection_points: Optional inflection points
        config: Drift configuration
        
    Returns:
        List of (start_seq, end_seq) tuples
    """
    if not snapshots:
        return []
    
    # Strategy 1: Use inflection points
    if inflection_points:
        segments = []
        inflection_seqs = sorted([ip.seq for ip in inflection_points])
        
        start_seq = snapshots[0].seq
        for inflection_seq in inflection_seqs:
            segments.append((start_seq, inflection_seq - 1))
            start_seq = inflection_seq
        
        # Add final segment
        segments.append((start_seq, snapshots[-1].seq))
        return segments
    
    # Strategy 2: Fixed window size
    window_size = getattr(config, 'baseline_segment_window', None)
    if window_size:
        segments = []
        start_seq = snapshots[0].seq
        end_seq = start_seq + window_size - 1
        
        while start_seq <= snapshots[-1].seq:
            segments.append((start_seq, min(end_seq, snapshots[-1].seq)))
            start_seq = end_seq + 1
            end_seq = start_seq + window_size - 1
        
        return segments
    
    # Strategy 3: Single segment (all snapshots)
    return [(snapshots[0].seq, snapshots[-1].seq)]


def _compute_median_baseline(
    normalized_snapshots: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute median baseline from normalized snapshots
    
    For each field, compute median value across all snapshots.
    Handles numeric, string, and nested structures.
    
    Args:
        normalized_snapshots: List of normalized parameter dicts
        
    Returns:
        Median baseline parameters
    """
    if not normalized_snapshots:
        return {}
    
    if len(normalized_snapshots) == 1:
        return normalized_snapshots[0].copy()
    
    # Flatten all snapshots
    all_fields = set()
    for snapshot in normalized_snapshots:
        all_fields.update(_flatten_dict_keys(snapshot))
    
    # Compute median for each field
    baseline = {}
    for field_path in all_fields:
        values = []
        for snapshot in normalized_snapshots:
            value = _get_nested_value(snapshot, field_path)
            if value is not None:
                values.append(value)
        
        if not values:
            continue
        
        # Compute median based on type
        median_value = _compute_median_value(values)
        _set_nested_value(baseline, field_path, median_value)
    
    return baseline


def _compute_percentile_baseline(
    normalized_snapshots: List[Dict[str, Any]],
    percentile: float,
) -> Dict[str, Any]:
    """
    Compute percentile baseline from normalized snapshots
    
    Similar to median but uses configurable percentile.
    
    Args:
        normalized_snapshots: List of normalized parameter dicts
        percentile: Percentile to use (0-100)
        
    Returns:
        Percentile baseline parameters
    """
    if not normalized_snapshots:
        return {}
    
    if len(normalized_snapshots) == 1:
        return normalized_snapshots[0].copy()
    
    # Flatten all snapshots
    all_fields = set()
    for snapshot in normalized_snapshots:
        all_fields.update(_flatten_dict_keys(snapshot))
    
    # Compute percentile for each field
    baseline = {}
    for field_path in all_fields:
        values = []
        for snapshot in normalized_snapshots:
            value = _get_nested_value(snapshot, field_path)
            if value is not None:
                values.append(value)
        
        if not values:
            continue
        
        # Compute percentile based on type
        percentile_value = _compute_percentile_value(values, percentile)
        _set_nested_value(baseline, field_path, percentile_value)
    
    return baseline


def _compute_median_value(values: List[Any]) -> Any:
    """Compute median value from list of values"""
    if not values:
        return None
    
    # Numeric values
    if all(isinstance(v, (int, float)) for v in values):
        return statistics.median(values)
    
    # String values: use most common
    if all(isinstance(v, str) for v in values):
        from collections import Counter
        counter = Counter(values)
        return counter.most_common(1)[0][0]
    
    # Boolean values: use majority
    if all(isinstance(v, bool) for v in values):
        return sum(values) > len(values) / 2
    
    # List values: use median length, then median elements
    if all(isinstance(v, list) for v in values):
        if not values:
            return []
        median_len = int(statistics.median([len(v) for v in values]))
        if median_len == 0:
            return []
        # Use first snapshot's list structure as template
        return values[0][:median_len] if values[0] else []
    
    # Default: use most common
    from collections import Counter
    counter = Counter(str(v) for v in values)
    return counter.most_common(1)[0][0]


def _compute_percentile_value(values: List[Any], percentile: float) -> Any:
    """Compute percentile value from list of values"""
    if not values:
        return None
    
    # Numeric values
    if all(isinstance(v, (int, float)) for v in values):
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100.0)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    # For non-numeric, fall back to median
    return _compute_median_value(values)


def _flatten_dict_keys(d: Dict[str, Any], prefix: str = "") -> List[str]:
    """Flatten nested dict keys to dot-separated paths"""
    keys = []
    for key, value in d.items():
        if key.startswith("_"):  # Skip metadata
            continue
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.extend(_flatten_dict_keys(value, full_key))
        else:
            keys.append(full_key)
    return keys


def _get_nested_value(d: Dict[str, Any], path: str) -> Any:
    """Get nested value by dot-separated path"""
    parts = path.split(".")
    current = d
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _set_nested_value(d: Dict[str, Any], path: str, value: Any) -> None:
    """Set nested value by dot-separated path"""
    parts = path.split(".")
    current = d
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def build_baseline_from_snapshots(
    snapshots: List[ParamSnapshot],
    config: Optional[DriftConfig] = None,
    inflection_points: Optional[List[InflectionPoint]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build baseline from parameter snapshots (alias for build_baseline)
    
    This function is an alias for build_baseline to maintain API consistency.
    
    Args:
        snapshots: List of parameter snapshots
        config: Optional drift configuration
        inflection_points: Optional inflection points for segmented baseline
    
    Returns:
        Dictionary mapping tool_name -> normalized baseline parameters
    """
    return build_baseline(snapshots, config, inflection_points)


__all__ = [
    "BaselineStrategy",
    "build_baseline",
    "build_baseline_from_snapshots",
]
