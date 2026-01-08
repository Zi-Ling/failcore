# failcore/web/routes/pages/run_detail.py
"""
Run Detail (Inspector) - three-column workbench for inspecting a single run.

Layout:
- Left: Timeline (events)
- Right: Inspector Panel (selected event details)
- Top: Action Bar (pluggable actions)
"""

import json
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from failcore.utils.paths import get_failcore_root
from failcore.web.services.actions_service import get_actions_service

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/run")


@router.get("/{date}/{run_name}", response_class=HTMLResponse)
async def run_detail(request: Request, date: str, run_name: str):
    """
    Run Detail page - Inspector workbench.
    
    This is the extensibility hub: all new actions appear in the Action Bar.
    """
    # Load run data
    trace_path = get_failcore_root() / "runs" / date / run_name / "trace.jsonl"
    
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Read trace events
    events = []
    try:
        with open(trace_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading trace: {e}")
    
    # Parse run info
    # Format: run_{id}_{timestamp}_{command} or {date}_{rest}
    # We need to extract the actual run_id for job creation
    # The run_id for jobs should be: {date}_{run_name}
    job_run_id = f"{date}_{run_name}"
    
    parts = run_name.split("_", 2)
    run_info = {
        "run_id": job_run_id,  # Use full identifier for job creation
        "timestamp": parts[1] if len(parts) > 1 else "",
        "command": parts[2] if len(parts) == 3 else "unknown",
        "date": date,
        "name": run_name,
        "total_events": len(events),
    }
    
    # Get available actions for this run
    actions_service = get_actions_service()
    actions = actions_service.get_actions("run")
    
    return templates.TemplateResponse(
        "pages/run_detail.html",
        {
            "request": request,
            "run_info": run_info,
            "events": events,
            "actions": actions,
        }
    )


__all__ = ["router"]
