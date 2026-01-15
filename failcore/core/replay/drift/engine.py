# failcore/core/replay/drift/engine.py
"""
Drift Engine

Real and NoOp implementations of parameter drift detection engine.
"""

from typing import Dict, Any
from .types import DriftResult, DriftSeverity, DriftDelta
from .rules import detect_drift as detect_drift_rules


class DriftEngine:
    """
    Parameter drift detection engine interface
    
    Both RealDriftEngine and NoOpDriftEngine implement this interface.
    """
    
    def detect_drift(self, current: Dict[str, Any], baseline: Dict[str, Any]) -> DriftResult:
        """
        Detect parameter drift between current and baseline
        
        Args:
            current: Current tool call parameters
            baseline: Baseline parameters (from golden trace or previous runs)
        
        Returns:
            DriftResult with drift information
        """
        raise NotImplementedError


class RealDriftEngine(DriftEngine):
    """
    Real Drift engine implementation
    
    Detects deterministic behavioral deviation in tool execution parameters.
    """
    
    def __init__(
        self,
        magnitude_threshold_medium: float = 2.0,
        magnitude_threshold_high: float = 5.0,
        ignore_fields: list[str] = None,
        analysis_only: bool = True,
    ):
        """
        Initialize real Drift engine
        
        Args:
            magnitude_threshold_medium: Threshold for medium severity (2.0 = 2x change)
            magnitude_threshold_high: Threshold for high severity (5.0 = 5x change)
            ignore_fields: Fields to ignore in drift detection
            analysis_only: If True, only analyze (never block)
        """
        self.magnitude_threshold_medium = magnitude_threshold_medium
        self.magnitude_threshold_high = magnitude_threshold_high
        self.ignore_fields = ignore_fields or []
        self.analysis_only = analysis_only
    
    def detect_drift(self, current: Dict[str, Any], baseline: Dict[str, Any]) -> DriftResult:
        """Detect drift using rule-based detection"""
        # Use existing detect_drift function - returns List[DriftChange]
        # Note: detect_drift_rules expects (baseline, current, tool_name, config)
        from .config import get_default_config
        config = get_default_config()
        changes = detect_drift_rules(baseline, current, "", config)
        
        # Convert to DriftResult
        deltas = []
        max_magnitude = 1.0
        change_types = set()
        
        for change in changes:
            # Calculate magnitude from change
            magnitude = 1.0
            if hasattr(change, 'magnitude'):
                magnitude = change.magnitude
            elif change.change_type == "magnitude_changed":
                # Estimate magnitude from severity
                if change.severity == "high":
                    magnitude = 10.0
                elif change.severity == "medium":
                    magnitude = 3.0
                else:
                    magnitude = 1.5
            
            delta = DriftDelta(
                path=change.field_path,
                old_value=change.baseline_value,
                new_value=change.current_value,
                change_type=change.change_type,
                magnitude=magnitude,
            )
            deltas.append(delta)
            max_magnitude = max(max_magnitude, magnitude)
            change_types.add(change.change_type)
        
        # Calculate score (simple: number of changes weighted by severity)
        score = len(deltas) * 0.1  # Simple scoring
        
        # Determine severity
        if max_magnitude >= self.magnitude_threshold_high:
            severity = DriftSeverity.HIGH
        elif max_magnitude >= self.magnitude_threshold_medium:
            severity = DriftSeverity.MEDIUM
        elif max_magnitude > 1.0:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE
        
        return DriftResult(
            drifted=len(deltas) > 0,
            score=score,
            severity=severity,
            deltas=deltas,
            reason="ok",
            evidence={
                "analysis_only": self.analysis_only,
                "change_types": list(change_types),
            },
        )


class NoOpDriftEngine(DriftEngine):
    """
    NoOp Drift engine when module is disabled
    
    Returns no drift with reason="disabled" for observability.
    """
    
    def detect_drift(self, current: Dict[str, Any], baseline: Dict[str, Any]) -> DriftResult:
        """NoOp detect - returns no drift"""
        return DriftResult(
            drifted=False,
            score=0.0,
            severity=DriftSeverity.NONE,
            deltas=[],
            reason="disabled",
            evidence={
                "status": "disabled",
            },
        )
    
    def __repr__(self) -> str:
        return "NoOpDriftEngine(disabled)"


__all__ = [
    "DriftEngine",
    "RealDriftEngine",
    "NoOpDriftEngine",
]
