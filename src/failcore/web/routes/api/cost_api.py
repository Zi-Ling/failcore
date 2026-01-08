# failcore/web/routes/api/cost_api.py
"""
Cost API - expose cost tracking data

Provides REST endpoints for cost data:
- GET /api/runs/<run_id>/cost: Get cost curve, budget, and events
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from failcore.web.services.cost_service import get_cost_service

router = APIRouter(prefix="/api/runs", tags=["cost"])


@router.get("/{run_id}/cost")
async def get_run_cost(run_id: str) -> Dict[str, Any]:
    """
    Get cost data for a run
    
    Returns:
        {
            "points": [
                {
                    "seq": int,
                    "ts": str,
                    "delta_cost_usd": float,
                    "cum_cost_usd": float,
                    "delta_tokens": int,
                    "cum_tokens": int,
                    "delta_api_calls": int,
                    "cum_api_calls": int,
                    "status": str,
                    "tool": str,
                    "error_code": Optional[str],
                },
                ...
            ],
            "budget": {
                "max_cost_usd": Optional[float],
                "max_tokens": Optional[int],
                "max_usd_per_minute": Optional[float],
            },
            "events": [
                {
                    "seq": int,
                    "ts": str,
                    "reason": str,
                    "error_code": Optional[str],
                },
                ...
            ],
        }
    """
    try:
        cost_service = get_cost_service()
        result = cost_service.get_run_cost(run_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cost data: {str(e)}")


__all__ = ["router"]
