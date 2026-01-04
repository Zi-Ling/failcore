# failcore/web/routes/pages/replay.py
"""
Replay Page - incident replay viewer page route

Provides the replay viewer page (tape view) for a specific run.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from failcore.web.services.replay_service import get_replay_service

router = APIRouter()
templates = Jinja2Templates(directory="failcore/web/templates")


@router.get("/runs/{run_id}/replay", response_class=HTMLResponse, name="replay")
async def view_replay(run_id: str, request: Request):
    """
    Replay viewer page for a specific run.
    
    Shows the "tape view" with:
    - Left: Timeline (frame list)
    - Center: Inspector (diff + highlights)
    - Right: Narrative / Evidence / Cost
    """
    try:
        replay_service = get_replay_service()
        incident_tape = replay_service.get_incident_tape(run_id)
        
        return templates.TemplateResponse(
            "pages/replay.html",
            {
                "request": request,
                "run_id": run_id,
                "incident_tape": incident_tape.to_dict(),
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load replay: {str(e)}")


__all__ = ["router"]
