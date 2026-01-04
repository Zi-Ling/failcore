# failcore/web/routes/api/replay_api.py
"""
Replay API - incident replay viewer data endpoint

Provides API endpoint for loading replay data (incident tape).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from failcore.web.services.replay_service import get_replay_service

router = APIRouter(prefix="/api/runs")


@router.get("/{run_id}/replay", tags=["Replay"], summary="Get incident replay data for a run")
async def get_replay_data(run_id: str):
    """
    Get incident replay data (incident tape) for a specific run.
    
    Returns:
        {
            "run_id": str,
            "meta": RunMeta,
            "frames": List[StepFrame],
            "events": List[IncidentEvent],
            "budget": CostBudget,
            "cost_curve": List[CostPoint],
        }
    """
    try:
        replay_service = get_replay_service()
        incident_tape = replay_service.get_incident_tape(run_id)
        
        # Convert to dict for JSON serialization
        return JSONResponse(incident_tape.to_dict())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load replay data: {str(e)}")


__all__ = ["router"]
