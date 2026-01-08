# failcore/web/services/drift_service.py
"""
Drift Service - provides drift analysis data for web UI

Service layer for drift detection, wraps core replay drift engine.
"""

from typing import Dict, Any, List, Optional

from .repos.trace_repo import TraceRepo


class DriftService:
    """
    Service for drift detection and analysis
    
    Provides drift analysis data for web UI consumption.
    """
    
    def __init__(self, trace_repo: Optional[TraceRepo] = None):
        """
        Initialize drift service
        
        Args:
            trace_repo: Optional trace repository (creates default if None)
        """
        from .repos.trace_repo import TraceRepo
        self.trace_repo = trace_repo or TraceRepo()
    
    def get_drift_analysis(self, run_id: str) -> Dict[str, Any]:
        """
        Get drift analysis for a run
        
        Args:
            run_id: Run ID
        
        Returns:
            Dictionary containing drift analysis data:
            {
                "run_id": str,
                "drift_points": List[DriftPoint],
                "inflection_points": List[InflectionPoint],
                "annotations": List[DriftAnnotation],
            }
        """
        # Load trace events
        events = self.trace_repo.load_trace_events(run_id)
        
        if not events:
            return {
                "run_id": run_id,
                "drift_points": [],
                "inflection_points": [],
                "annotations": [],
            }
        
        # Compute drift
        from failcore.core.replay.drift import compute_drift
        drift_result = compute_drift(events)
        
        # Convert to dict for JSON serialization
        return {
            "run_id": run_id,
            "drift_points": [dp.to_dict() for dp in drift_result.drift_points],
            "inflection_points": [ip.to_dict() for ip in drift_result.inflection_points],
            "annotations": [a.to_dict() for a in drift_result.annotations],
        }


# Singleton instance
_drift_service: Optional[DriftService] = None


def get_drift_service() -> DriftService:
    """Get drift service singleton"""
    global _drift_service
    if _drift_service is None:
        _drift_service = DriftService()
    return _drift_service


__all__ = ["DriftService", "get_drift_service"]
