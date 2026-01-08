# failcore/core/replay/drift/__init__.py
"""
Parameter Drift Engine - detects deterministic behavioral deviation in tool execution parameters

The Drift Engine operates on execution-time traces and produces evidence suitable for audit, replay, and human review.
"""

from typing import Union, List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass

from .types import (
    ParamSnapshot,
    DriftChange,
    DriftPoint,
    DriftAnnotation,
)
from .inflection import InflectionPoint
from .extract import extract_param_snapshots
from .normalize import normalize_params
from .baseline import build_baseline
from .config import get_default_config, DriftConfig
from .rules import detect_drift
from .scoring import compute_drift_points
from .inflection import detect_inflection_points
from .annotate import annotate_drift, annotate_all_drift_points


@dataclass
class DriftResult:
    """
    Complete drift analysis result
    
    Contains all drift-related data computed from a trace.
    """
    snapshots: List[ParamSnapshot]  # Parameter snapshots extracted
    baselines: Dict[str, Dict[str, Any]]  # Baselines per tool
    drift_points: List[DriftPoint]  # Drift points (one per snapshot)
    inflection_points: List[InflectionPoint]  # Inflection points detected
    annotations: List[DriftAnnotation]  # UI-friendly annotations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "snapshots": [s.to_dict() for s in self.snapshots],
            "baselines": self.baselines,
            "drift_points": [p.to_dict() for p in self.drift_points],
            "inflection_points": [ip.to_dict() for ip in self.inflection_points],
            "annotations": [a.to_dict() for a in self.annotations],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DriftResult":
        """Create from dictionary"""
        from .types import ParamSnapshot, DriftPoint, InflectionPoint, DriftAnnotation
        
        return cls(
            snapshots=[ParamSnapshot.from_dict(s) for s in data["snapshots"]],
            baselines=data["baselines"],
            drift_points=[DriftPoint.from_dict(p) for p in data["drift_points"]],
            inflection_points=[InflectionPoint.from_dict(ip) for ip in data["inflection_points"]],
            annotations=[DriftAnnotation.from_dict(a) for a in data["annotations"]],
        )


def compute_drift(
    trace_path_or_events: Union[str, Path, List[Dict[str, Any]]],
    config: Optional[DriftConfig] = None,
) -> DriftResult:
    """
    Compute drift analysis from trace
    
    This is the main entry point for drift detection.
    Accepts either a trace file path or a list of trace events.
    
    Args:
        trace_path_or_events: Trace file path (str/Path) or list of trace events (dicts)
        config: Optional drift configuration (uses default if None)
    
    Returns:
        DriftResult containing all drift analysis data
    
    Example:
        >>> from failcore.core.replay.drift import compute_drift
        >>> result = compute_drift("trace.jsonl")
        >>> print(f"Found {len(result.inflection_points)} inflection points")
    """
    if config is None:
        config = get_default_config()
    
    # Load events if path provided
    if isinstance(trace_path_or_events, (str, Path)):
        events = _load_trace_events(trace_path_or_events)
    else:
        events = trace_path_or_events
    
    # Extract parameter snapshots
    snapshots = extract_param_snapshots(events)
    
    if not snapshots:
        # No snapshots found, return empty result
        return DriftResult(
            snapshots=[],
            baselines={},
            drift_points=[],
            inflection_points=[],
            annotations=[],
        )
    
    # Build baselines
    baselines = build_baseline(snapshots, config)
    
    # Compute drift points
    drift_points = compute_drift_points(snapshots, baselines, config)
    
    # Detect inflection points
    inflection_points = detect_inflection_points(drift_points, config)
    
    # Generate annotations
    annotations = annotate_all_drift_points(drift_points, inflection_points)
    
    return DriftResult(
        snapshots=snapshots,
        baselines=baselines,
        drift_points=drift_points,
        inflection_points=inflection_points,
        annotations=annotations,
    )


def _load_trace_events(trace_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Load trace events from file
    
    Args:
        trace_path: Path to trace.jsonl file
    
    Returns:
        List of trace events
    """
    import json
    
    trace_path = Path(trace_path)
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_path}")
    
    events = []
    with open(trace_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    
    return events


__all__ = [
    "ParamSnapshot",
    "DriftChange",
    "DriftPoint",
    "InflectionPoint",
    "DriftAnnotation",
    "DriftResult",
    "extract_param_snapshots",
    "normalize_params",
    "build_baseline",
    "detect_drift",
    "compute_drift_points",
    "detect_inflection_points",
    "annotate_all_drift_points",
    "compute_drift",
    "get_default_config",
    "DriftConfig",
]
