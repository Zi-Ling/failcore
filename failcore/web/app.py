# failcore/web/app.py
"""
FastAPI application for FailCore Web UI.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# Get package directory
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="FailCore Web UI",
        description="Observable and replayable tool execution engine",
        version="0.1.2",
    )
    
    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Register routes
    from .routes.pages import overview, runs, run_detail, jobs
    from .routes.api import actions_api, jobs_api, artifacts_api
    
    # Page routes
    app.include_router(overview.router)
    app.include_router(runs.router)
    app.include_router(run_detail.router)
    app.include_router(jobs.router)
    
    # API routes
    app.include_router(actions_api.router)
    app.include_router(jobs_api.router)
    app.include_router(artifacts_api.router)
    
    return app


__all__ = ["create_app"]
