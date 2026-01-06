# failcore/core/replay/drift/annotate.py
"""
Drift Annotation Generator - produces UI-friendly annotations for replay viewer

Generates annotations that can be consumed by the replay UI without any computation.
UI layer only displays annotations, all drift logic is done here.
"""

from typing import List, Optional, Dict, Any

from .types import DriftPoint, DriftChange, DriftAnnotation
from .inflection import InflectionPoint


def annotate_drift(
    drift_point: DriftPoint,
    inflection_points: Optional[List[InflectionPoint]] = None,
) -> Optional[DriftAnnotation]:
    """
    Generate UI-friendly annotation for a drift point
    
    Args:
        drift_point: Drift point to annotate
        inflection_points: Optional list of inflection points (to check if this is an inflection)
    
    Returns:
        DriftAnnotation if drift detected, None otherwise
    """
    if drift_point.drift_delta == 0.0:
        return None  # No drift, no annotation
    
    # Check if this is an inflection point
    is_inflection = False
    if inflection_points:
        for ip in inflection_points:
            if ip.seq == drift_point.seq:
                is_inflection = True
                break
    
    # Determine badge
    badge = "INFLECTION" if is_inflection else "DRIFT"
    
    # Determine severity based on drift_delta and change types
    severity = _determine_severity(drift_point)
    
    # Generate summary
    summary = _generate_summary(drift_point, is_inflection)
    
    # Get top changes (limit to 3 for tooltip)
    changes = _format_changes(drift_point.top_changes[:3])
    
    return DriftAnnotation(
        badge=badge,
        severity=severity,
        summary=summary,
        changes=changes,
    )


def _determine_severity(drift_point: DriftPoint) -> str:
    """
    Determine severity based on drift delta and change types
    
    Args:
        drift_point: Drift point
    
    Returns:
        Severity: "info", "warn", or "high"
    """
    # Check for high-severity change types
    has_domain_changed = any(
        c.change_type == "domain_changed" for c in drift_point.top_changes
    )
    has_high_magnitude = any(
        c.change_type == "magnitude_changed" and c.severity == "high"
        for c in drift_point.top_changes
    )
    
    if has_domain_changed or drift_point.drift_delta >= 10.0:
        return "high"
    elif has_high_magnitude or drift_point.drift_delta >= 5.0:
        return "warn"
    else:
        return "info"


def _generate_summary(drift_point: DriftPoint, is_inflection: bool) -> str:
    """
    Generate one-line summary for drift
    
    Args:
        drift_point: Drift point
        is_inflection: Whether this is an inflection point
    
    Returns:
        One-line summary string
    """
    if not drift_point.top_changes:
        return f"Drift detected: {drift_point.drift_delta:.1f} points"
    
    # Use the top change for summary
    top_change = drift_point.top_changes[0]
    
    # Format based on change type
    if top_change.change_type == "domain_changed":
        baseline_str = _format_value(top_change.baseline_value)
        current_str = _format_value(top_change.current_value)
        return f"Domain changed: {top_change.field_path} {baseline_str} → {current_str}"
    
    elif top_change.change_type == "magnitude_changed":
        baseline_str = _format_value(top_change.baseline_value)
        current_str = _format_value(top_change.current_value)
        return f"Magnitude changed: {top_change.field_path} {baseline_str} → {current_str}"
    
    else:  # value_changed
        baseline_str = _format_value(top_change.baseline_value)
        current_str = _format_value(top_change.current_value)
        prefix = "Inflection: " if is_inflection else ""
        return f"{prefix}Value changed: {top_change.field_path} {baseline_str} → {current_str}"


def _format_value(value: Any) -> str:
    """
    Format value for display in summary
    
    Args:
        value: Value to format
    
    Returns:
        Formatted string
    """
    if value is None:
        return "None"
    if isinstance(value, str):
        # Truncate long strings
        if len(value) > 30:
            return f'"{value[:27]}..."'
        return f'"{value}"'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (list, dict)):
        return f"{type(value).__name__}({len(value)})"
    return str(value)[:30]


def _format_changes(changes: List[DriftChange]) -> List[Dict[str, Any]]:
    """
    Format changes for tooltip/diff display
    
    Args:
        changes: List of drift changes
    
    Returns:
        List of formatted change dictionaries
    """
    formatted = []
    
    for change in changes:
        formatted.append({
            "field_path": change.field_path,
            "change_type": change.change_type,
            "severity": change.severity,
            "baseline_value": change.baseline_value,
            "current_value": change.current_value,
            "reason": change.reason,
        })
    
    return formatted


def annotate_all_drift_points(
    drift_points: List[DriftPoint],
    inflection_points: Optional[List[InflectionPoint]] = None,
) -> List[DriftAnnotation]:
    """
    Generate annotations for all drift points
    
    Args:
        drift_points: List of drift points
        inflection_points: Optional list of inflection points
    
    Returns:
        List of annotations (one per drift point, None entries filtered out)
    """
    annotations = []
    
    for drift_point in drift_points:
        annotation = annotate_drift(drift_point, inflection_points)
        if annotation:
            annotations.append(annotation)
    
    return annotations


__all__ = ["annotate_drift", "annotate_all_drift_points"]
