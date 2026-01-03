# failcore/web/routes/api/artifacts_api.py
"""
Artifacts API - access job outputs (reports, audits, exports, diffs).

All outputs flow through here for unified preview/download.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from failcore.web.services.artifacts_service import get_artifacts_service
from failcore.web.services.jobs_service import get_jobs_service

router = APIRouter(prefix="/api/artifacts")


@router.get("/runs/{date}/{run_name}/artifacts")
async def list_run_artifacts(date: str, run_name: str):
    """
    List all artifacts for a specific run.
    
    Returns:
    - Reports (HTML/JSON)
    - Audits (JSON/HTML)
    - Traces (JSONL export)
    - Any other outputs
    """
    from failcore.utils.paths import get_failcore_root
    import json
    
    run_dir = get_failcore_root() / "runs" / date / run_name
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    
    artifacts = []
    
    # Scan all potential artifacts
    artifact_patterns = [
        ("trace.jsonl", "trace", "jsonl", "json"),
        ("report.json", "report_json", "json", "json"),
        ("report.html", "report_html", "html", "html"),
        ("audit.json", "audit_json", "json", "json"),
        ("audit.html", "audit_html", "html", "html"),
        ("audit_report.html", "audit_report_html", "html", "html"),
    ]
    
    for filename, type_id, format_type, preview_mode in artifact_patterns:
        file_path = run_dir / filename
        if file_path.exists():
            artifacts.append({
                "artifact_id": f"{date}_{run_name}_{type_id}",
                "type": type_id,
                "format": format_type,
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "preview_mode": preview_mode,
                "name": filename,
            })
    
    return {
        "run_id": run_name,
        "artifacts": artifacts,
        "total": len(artifacts),
    }


@router.get("/jobs/{job_id}/artifacts")
async def list_job_artifacts(job_id: str):
    """
    List artifacts produced by a specific job.
    
    Used to show job results in Jobs page.
    """
    jobs_service = get_jobs_service()
    job = jobs_service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.artifacts:
        return {"artifacts": [], "message": "No artifacts yet"}
    
    return {
        "job_id": job_id,
        "artifacts": job.artifacts,
        "total": len(job.artifacts),
    }


@router.get("/{artifact_id}")
async def get_artifact_metadata(artifact_id: str):
    """
    Get artifact metadata (type, size, preview mode, etc.).
    
    Does NOT return content - use /preview or /download for that.
    """
    artifacts_service = get_artifacts_service()
    artifact = artifacts_service.get_artifact(artifact_id)
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    return {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "mime": artifact.mime,
        "size": artifact.size,
        "preview_mode": artifact.preview_mode,
        "created_at": artifact.created_at,
    }


@router.get("/{artifact_id}/preview")
async def preview_artifact(artifact_id: str):
    """
    Get artifact content for preview (inline display).
    
    Returns:
    - HTML: rendered in iframe
    - JSON/JSONL: syntax-highlighted viewer
    - Text: code block
    """
    from failcore.utils.paths import get_failcore_root
    import json
    
    # Parse artifact_id: {date}_{run_name}_{type_id}
    parts = artifact_id.split("_")
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Invalid artifact_id format")
    
    date = parts[0]
    
    # Find type_id by checking known patterns
    type_patterns = ["trace", "report_json", "report_html", "audit_json", "audit_html", "audit_report_html"]
    type_id = None
    run_name = None
    
    for pattern in type_patterns:
        pattern_parts = pattern.split("_")
        if len(parts) >= len(pattern_parts) + 2:  # date + run_name + type
            candidate_type = "_".join(parts[-(len(pattern_parts)):])
            if candidate_type == pattern:
                type_id = pattern
                run_name = "_".join(parts[1:-(len(pattern_parts))])
                break
    
    if not type_id or not run_name:
        raise HTTPException(status_code=400, detail="Could not parse artifact_id")
    
    # Map type_id to filename
    file_map = {
        "trace": "trace.jsonl",
        "report_json": "report.json",
        "report_html": "report.html",
        "audit_json": "audit.json",
        "audit_html": "audit.html",
        "audit_report_html": "audit_report.html",
    }
    
    filename = file_map.get(type_id)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unknown type_id: {type_id}")
    
    run_dir = get_failcore_root() / "runs" / date / run_name
    file_path = run_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Determine preview mode
        if filename.endswith('.html'):
            return JSONResponse({"format": "html", "content": content})
        elif filename.endswith('.json') or filename.endswith('.jsonl'):
            return JSONResponse({"format": "json", "content": content})
        else:
            return JSONResponse({"format": "text", "content": content})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read artifact: {e}")


@router.get("/download/{artifact_id}")
async def download_artifact(artifact_id: str):
    """
    Download artifact as file attachment.
    
    Triggers browser download prompt.
    """
    from failcore.utils.paths import get_failcore_root
    
    # Parse artifact_id: {date}_{run_name}_{type_id}
    parts = artifact_id.split("_")
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Invalid artifact_id format")
    
    date = parts[0]
    
    # Find type_id by checking known patterns
    type_patterns = ["trace", "report_json", "report_html", "audit_json", "audit_html", "audit_report_html"]
    type_id = None
    run_name = None
    
    for pattern in type_patterns:
        pattern_parts = pattern.split("_")
        if len(parts) >= len(pattern_parts) + 2:  # date + run_name + type
            candidate_type = "_".join(parts[-(len(pattern_parts)):])
            if candidate_type == pattern:
                type_id = pattern
                run_name = "_".join(parts[1:-(len(pattern_parts))])
                break
    
    if not type_id or not run_name:
        raise HTTPException(status_code=400, detail="Could not parse artifact_id")
    
    # Map type_id to filename
    file_map = {
        "trace": "trace.jsonl",
        "report_json": "report.json",
        "report_html": "report.html",
        "audit_json": "audit.json",
        "audit_html": "audit.html",
        "audit_report_html": "audit_report.html",
    }
    
    filename = file_map.get(type_id)
    if not filename:
        raise HTTPException(status_code=400, detail=f"Unknown type_id: {type_id}")
    
    run_dir = get_failcore_root() / "runs" / date / run_name
    file_path = run_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact file not found: {filename}")
    
    # Determine MIME type
    mime_map = {
        ".jsonl": "application/x-ndjson",
        ".json": "application/json",
        ".html": "text/html",
    }
    mime_type = mime_map.get(file_path.suffix, "application/octet-stream")
    
    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=file_path.name,
    )


__all__ = ["router"]
