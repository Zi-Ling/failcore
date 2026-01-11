"""
Policy management pages
"""

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ....core.validate.loader import get_policy_dir

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/policy", response_class=HTMLResponse)
async def policy_overview(request: Request):
    """Policy overview page"""
    try:
        policy_dir = get_policy_dir()
        policy_exists = policy_dir.exists()
    except:
        policy_dir = None
        policy_exists = False
    
    return templates.TemplateResponse(
        "policy/overview.html",
        {
            "request": request,
            "policy_dir": str(policy_dir) if policy_dir else None,
            "policy_exists": policy_exists
        }
    )


@router.get("/policy/validators", response_class=HTMLResponse)
async def validators_list(request: Request):
    """List all available validators"""
    return templates.TemplateResponse(
        "policy/validators.html",
        {"request": request}
    )


@router.get("/policy/editor/{policy_type}", response_class=HTMLResponse)
async def policy_editor(request: Request, policy_type: str):
    """Policy editor page"""
    if policy_type not in ['active', 'shadow', 'breakglass', 'merged']:
        return HTMLResponse("Invalid policy type", status_code=400)
    
    return templates.TemplateResponse(
        "policy/editor.html",
        {
            "request": request,
            "policy_type": policy_type
        }
    )


@router.get("/policy/explain", response_class=HTMLResponse)
async def policy_explain(request: Request):
    """Policy explain tool"""
    return templates.TemplateResponse(
        "policy/explain.html",
        {"request": request}
    )


@router.get("/policy/diff", response_class=HTMLResponse)
async def policy_diff(request: Request):
    """Policy diff tool"""
    return templates.TemplateResponse(
        "policy/diff.html",
        {"request": request}
    )
