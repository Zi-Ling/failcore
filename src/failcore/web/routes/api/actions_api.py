# failcore/web/routes/api/actions_api.py
"""
Actions API - query available actions (metadata only).

Actions are NOT executed here. Execution goes through jobs_api.py.
"""

from fastapi import APIRouter, Query
from typing import Optional

from failcore.web.services.actions_service import get_actions_service, ActionScope

router = APIRouter(prefix="/api/actions")


@router.get("/")
async def list_actions(
    scope: Optional[ActionScope] = Query(None, description="Filter by scope: run/trace/global"),
    run_id: Optional[str] = Query(None, description="Context run ID (for capability checks)"),
):
    """
    Get available actions (buttons) for UI rendering.
    
    This endpoint returns metadata only. To execute an action, POST to /api/jobs.
    """
    actions_service = get_actions_service()
    
    if scope:
        actions = actions_service.get_actions(scope, check_capabilities=True)
    else:
        # Return all scopes
        actions = []
        for s in ["global", "run", "trace"]:
            actions.extend(actions_service.get_actions(s, check_capabilities=True))
    
    return {
        "actions": [
            {
                "id": a.id,
                "label": a.label,
                "scope": a.scope,
                "icon": a.icon,
                "danger": a.danger,
                "description": a.description,
                "enabled": actions_service.is_allowed(a.id),
            }
            for a in actions
        ],
        "total": len(actions),
    }


@router.get("/{action_id}")
async def get_action(action_id: str):
    """Get metadata for a specific action."""
    actions_service = get_actions_service()
    action = actions_service.get_action(action_id)
    
    if not action:
        return {"error": "Action not found"}, 404
    
    return {
        "id": action.id,
        "label": action.label,
        "scope": action.scope,
        "method": action.method,
        "icon": action.icon,
        "danger": action.danger,
        "enabled": actions_service.is_allowed(action.id),
    }


__all__ = ["router"]
