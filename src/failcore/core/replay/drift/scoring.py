# failcore/core/replay/drift/scoring.py
"""
Drift Score Calculator - computes drift scores from parameter changes

Computes two types of scores:
1. drift_delta: Drift score for a single step (relative to baseline)
2. drift_cumulative: Cumulative drift score up to current step

Score calculation is explainable: score = Σ(w_i * diff_i)
where w_i is the weight for change type i and diff_i is the count/severity of changes.
"""

from typing import Dict, Any, List, Optional

from .types import ParamSnapshot, DriftPoint, DriftChange
from .config import DriftConfig, get_default_config
from .normalize import normalize_params
from .rules import detect_drift


def compute_drift_points(
    snapshots: List[ParamSnapshot],
    baselines: Dict[str, Dict[str, Any]],
    config: Optional[DriftConfig] = None,
) -> List[DriftPoint]:
    """
    Compute drift points for all snapshots
    
    Args:
        snapshots: List of parameter snapshots (ordered by seq)
        baselines: Dictionary mapping tool_name -> normalized baseline parameters
        config: Optional drift configuration (uses default if None)
    
    Returns:
        List of DriftPoint objects (ordered by seq)
    """
    if config is None:
        config = get_default_config()
    
    drift_points = []
    cumulative_score = 0.0
    
    for snapshot in snapshots:
        tool_name = snapshot.tool_name
        baseline_params = baselines.get(tool_name, {})
        
        # Normalize current parameters
        current_normalized = normalize_params(
            snapshot.params,
            tool_name,
            config,
        )
        
        # Detect drift
        changes = detect_drift(
            baseline_params,
            current_normalized,
            tool_name,
            config,
        )
        
        # Compute drift delta (score for this step)
        drift_delta = _compute_drift_score(changes, config)
        
        # Update cumulative score
        cumulative_score += drift_delta
        
        # Get top changes (sorted by severity)
        top_changes = _get_top_changes(changes, limit=5)
        
        # Create drift point
        drift_point = DriftPoint(
            seq=snapshot.seq,
            ts=snapshot.ts,
            tool=tool_name,
            drift_delta=drift_delta,
            drift_cumulative=cumulative_score,
            top_changes=top_changes,
            step_id=snapshot.step_id,
        )
        
        drift_points.append(drift_point)
    
    return drift_points


def _compute_drift_score(changes: List[DriftChange], config: DriftConfig) -> float:
    """
    Compute drift score from changes
    
    Score = Σ(w_i * count_i) where:
    - w_i is the weight for change type i
    - count_i is the count of changes of type i
    
    Args:
        changes: List of drift changes
        config: Drift configuration
    
    Returns:
        Drift score (float)
    """
    if not changes:
        return 0.0
    
    score = 0.0
    
    # Count changes by type
    value_changed_count = sum(1 for c in changes if c.change_type == "value_changed")
    magnitude_changed_count = sum(1 for c in changes if c.change_type == "magnitude_changed")
    domain_changed_count = sum(1 for c in changes if c.change_type == "domain_changed")
    
    # Apply weights
    score += value_changed_count * config.drift_weight_value_changed
    score += magnitude_changed_count * config.drift_weight_magnitude_changed
    score += domain_changed_count * config.drift_weight_domain_changed
    
    return score


def _get_top_changes(changes: List[DriftChange], limit: int = 5) -> List[DriftChange]:
    """
    Get top changes by severity
    
    Args:
        changes: List of drift changes
        limit: Maximum number of changes to return
    
    Returns:
        Top changes (sorted by severity: high > medium > low)
    """
    if not changes:
        return []
    
    # Sort by severity (high > medium > low)
    severity_order = {"high": 3, "medium": 2, "low": 1}
    
    sorted_changes = sorted(
        changes,
        key=lambda c: (
            severity_order.get(c.severity, 0),
            c.change_type == "domain_changed",  # Domain changes first
            c.change_type == "magnitude_changed",  # Then magnitude
        ),
        reverse=True,
    )
    
    return sorted_changes[:limit]


__all__ = ["compute_drift_points"]
