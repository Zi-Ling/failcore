# failcore/web/routes/pages/jobs.py
"""
Jobs page - background task queue and results.
"""

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from failcore.web.services.jobs_service import get_jobs_service

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/jobs")


@router.get("/", response_class=HTMLResponse)
async def jobs_list(request: Request):
    """
    Jobs page - view all background tasks.
    
    All async operations (report, audit, replay, run) go here.
    """
    jobs_service = get_jobs_service()
    jobs = jobs_service.list_jobs(limit=100)
    
    # Group by status
    stats = {
        "running": len([j for j in jobs if j.status == "running"]),
        "queued": len([j for j in jobs if j.status == "queued"]),
        "success": len([j for j in jobs if j.status == "success"]),
        "failed": len([j for j in jobs if j.status == "failed"]),
    }
    
    return templates.TemplateResponse(
        "pages/jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "stats": stats,
        }
    )


__all__ = ["router"]
