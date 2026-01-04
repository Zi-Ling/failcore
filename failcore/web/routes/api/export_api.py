# failcore/web/routes/api/export_api.py
"""
Export API - export incident replay as static files
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from failcore.web.services.export_service import get_export_service

router = APIRouter(prefix="/api/runs")


@router.post("/{run_id}/export/replay")
async def export_replay(run_id: str):
    """
    Export incident replay as standalone HTML file.
    
    Args:
        run_id: Run ID
    
    Returns:
        HTML file download
    """
    try:
        export_service = get_export_service()
        output_path = export_service.export_replay_html(run_id)
        
        if not output_path.exists():
            raise HTTPException(status_code=500, detail="Failed to generate export file")
        
        return FileResponse(
            path=str(output_path),
            filename=output_path.name,
            media_type="text/html",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export replay: {str(e)}")


__all__ = ["router"]
