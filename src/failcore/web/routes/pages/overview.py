# failcore/web/routes/overview.py
"""
Overview route - main dashboard showing threats, runs, and recent activity.
"""

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from failcore.utils.paths import get_failcore_root

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def _analyze_run_status(run_dir: Path) -> dict:
    """Analyze run status by checking trace events."""
    trace_file = run_dir / "trace.jsonl"
    if not trace_file.exists():
        return {"status": "NO_TRACE", "color": "gray"}
    
    # Quick scan for blocked/error events
    try:
        import json
        blocked_count = 0
        error_count = 0
        
        with open(trace_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    event_type = event.get("event_type") or event.get("type", "")
                    
                    # Check for validation/policy blocks
                    if event_type == "error":
                        data = event.get("data", {})
                        validation_type = data.get("validation_type", "")
                        code = data.get("code", "")
                        
                        if validation_type == "precondition" or code in ["SANDBOX_VIOLATION", "PATH_TRAVERSAL"]:
                            blocked_count += 1
                        else:
                            error_count += 1
                except:
                    continue
        
        if blocked_count > 0:
            return {"status": "BLOCKED", "color": "red", "count": blocked_count}
        elif error_count > 0:
            return {"status": "ERROR", "color": "yellow", "count": error_count}
        else:
            return {"status": "SUCCESS", "color": "green"}
    except:
        return {"status": "UNKNOWN", "color": "gray"}


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request):
    """Main overview page - security console style."""
    runs_dir = get_failcore_root() / "runs"
    recent_runs = []
    
    # Statistics
    total_runs = 0
    blocked_count = 0
    error_count = 0
    success_count = 0
    
    if runs_dir.exists():
        all_runs = []
        for date_dir in runs_dir.iterdir():
            if date_dir.is_dir():
                for run_dir in date_dir.iterdir():
                    if run_dir.is_dir():
                        total_runs += 1
                        
                        # Parse run info
                        parts = run_dir.name.split("_", 2)
                        run_command = parts[2] if len(parts) == 3 else "unknown"
                        
                        # Analyze status
                        status_info = _analyze_run_status(run_dir)
                        
                        if status_info["status"] == "BLOCKED":
                            blocked_count += 1
                        elif status_info["status"] == "ERROR":
                            error_count += 1
                        elif status_info["status"] == "SUCCESS":
                            success_count += 1
                        
                        all_runs.append({
                            "path": run_dir,
                            "name": run_dir.name,
                            "run_id": parts[0] if parts else run_dir.name,
                            "timestamp": parts[1] if len(parts) > 1 else "",
                            "command": run_command,
                            "date": date_dir.name,
                            "mtime": run_dir.stat().st_mtime,
                            "status": status_info["status"],
                            "status_color": status_info["color"],
                            "has_trace": (run_dir / "trace.jsonl").exists(),
                        })
        
        # Sort by modification time (newest first)
        all_runs.sort(key=lambda x: x["mtime"], reverse=True)
        recent_runs = all_runs[:15]  # Show latest 15
    
    stats = {
        "total_runs": total_runs,
        "blocked": blocked_count,
        "errors": error_count,
        "success": success_count,
    }
    
    return templates.TemplateResponse(
        "pages/overview.html",
        {
            "request": request,
            "recent_runs": recent_runs,
            "stats": stats,
        }
    )


__all__ = ["router"]
