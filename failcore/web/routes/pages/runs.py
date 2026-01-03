# failcore/web/routes/runs.py
"""
Runs route - list and filter all execution runs.
"""

from pathlib import Path
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from failcore.utils.paths import get_failcore_root

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/runs")


@router.get("/", response_class=HTMLResponse)
async def list_runs(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    command: str = Query(None),
):
    """List all runs with optional filtering."""
    runs_dir = get_failcore_root() / "runs"
    all_runs = []
    
    if runs_dir.exists():
        for date_dir in runs_dir.iterdir():
            if date_dir.is_dir():
                for run_dir in date_dir.iterdir():
                    if run_dir.is_dir():
                        # Parse run directory name: <run_id>_<HHMMSS>_<command>
                        parts = run_dir.name.split("_", 2)
                        run_command = parts[2] if len(parts) == 3 else "unknown"
                        
                        # Filter by command if specified
                        if command and run_command != command:
                            continue
                        
                        trace_file = run_dir / "trace.jsonl"
                        all_runs.append({
                            "path": run_dir,
                            "name": run_dir.name,
                            "run_id": parts[0] if parts else run_dir.name,
                            "timestamp": parts[1] if len(parts) > 1 else "",
                            "command": run_command,
                            "date": date_dir.name,
                            "mtime": run_dir.stat().st_mtime,
                            "has_trace": trace_file.exists(),
                        })
        
        # Sort by modification time (newest first)
        all_runs.sort(key=lambda x: x["mtime"], reverse=True)
        all_runs = all_runs[:limit]
    
    return templates.TemplateResponse(
        "pages/runs.html",
        {
            "request": request,
            "runs": all_runs,
            "filter_command": command,
            "limit": limit,
        }
    )


__all__ = ["router"]
