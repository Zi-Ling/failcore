# failcore/web/routes/api/drift_api.py
"""
Drift API - drift analysis data endpoint

Provides API endpoint for loading drift analysis data.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from failcore.web.services.drift_service import get_drift_service

router = APIRouter(prefix="/api/runs")


@router.get("/{run_id}/drift", tags=["Drift"], summary="Get drift analysis data for a run")
async def get_drift_data(run_id: str):
    """
    Get drift analysis data for a specific run.
    
    Returns:
        {
            "run_id": str,
            "drift_points": List[DriftPoint],
            "inflection_points": List[InflectionPoint],
            "annotations": List[DriftAnnotation],
        }
    """
    try:
        drift_service = get_drift_service()
        drift_analysis = drift_service.get_drift_analysis(run_id)
        
        return JSONResponse(drift_analysis)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load drift data: {str(e)}")


__all__ = ["router"]
