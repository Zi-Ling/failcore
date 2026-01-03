# failcore/web/routes/traces.py
"""
Traces route - view individual trace details.
"""

import json
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from failcore.utils.paths import get_failcore_root

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/traces")


@router.get("/{date}/{run_name}", response_class=HTMLResponse)
async def view_trace(request: Request, date: str, run_name: str):
    """View a specific trace."""
    # Construct path
    trace_path = get_failcore_root() / "runs" / date / run_name / "trace.jsonl"
    
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail="Trace not found")
    
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
    
    # Parse run info from name
    parts = run_name.split("_", 2)
    run_info = {
        "run_id": parts[0] if parts else run_name,
        "timestamp": parts[1] if len(parts) > 1 else "",
        "command": parts[2] if len(parts) == 3 else "unknown",
        "date": date,
        "total_events": len(events),
    }
    
    return templates.TemplateResponse(
        "pages/trace.html",
        {
            "request": request,
            "run_info": run_info,
            "events": events,
        }
    )


__all__ = ["router"]
