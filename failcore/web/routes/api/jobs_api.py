# failcore/web/routes/api/jobs_api.py
"""
Jobs API - create and query background tasks.

All action execution flows through here (not through actions_api).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from failcore.web.services.jobs_service import get_jobs_service, JobType, JobStatus
from failcore.web.services.actions_service import get_actions_service

router = APIRouter(prefix="/api/jobs")


class CreateJobRequest(BaseModel):
    """Request to create a new job."""
    action_id: str              # e.g. "report.generate"
    run_id: Optional[str] = None
    params: dict = {}


@router.post("/")
async def create_job(req: CreateJobRequest):
    """
    Create a new background job (unified entry for all actions).
    
    Flow:
    1. User clicks action button in UI
    2. Frontend POSTs here with action_id
    3. We validate capability and create job
    4. Job executes (sync for now, async later)
    5. Frontend polls GET /api/jobs/{job_id} for status
    """
    actions_service = get_actions_service()
    
    # Validate action exists and is allowed
    action = actions_service.get_action(req.action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{req.action_id}' not found")
    
    if not actions_service.is_allowed(req.action_id):
        raise HTTPException(
            status_code=403, 
            detail=f"Action '{req.action_id}' not allowed (check capability flags)"
        )
    
    # Map action to job type
    job_type_map = {
        "report.generate": "report",
        "audit.generate": "audit",
        "trace.export": "export",
        "replay.run": "replay",
    }
    
    job_type = job_type_map.get(req.action_id)
    if not job_type:
        raise HTTPException(status_code=400, detail=f"Action '{req.action_id}' not mapped to job type")
    
    # Create job
    jobs_service = get_jobs_service()
    job = jobs_service.create_job(
        job_type=job_type,
        inputs={
            "action_id": req.action_id,
            "run_id": req.run_id,
            **req.params,
        }
    )
    
    # Execute (for now, synchronously; future: enqueue to worker)
    jobs_service.execute_job(job.job_id)
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": f"Job {job.job_id} created and executed",
    }


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get job status and results."""
    jobs_service = get_jobs_service()
    job = jobs_service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job.to_dict()


@router.get("/")
async def list_jobs(
    limit: int = 50,
    status: Optional[JobStatus] = None,
    job_type: Optional[JobType] = None,
):
    """List jobs with optional filtering."""
    jobs_service = get_jobs_service()
    jobs = jobs_service.list_jobs(limit=limit, status=status, job_type=job_type)
    
    return {
        "jobs": [j.to_dict() for j in jobs],
        "total": len(jobs),
    }


__all__ = ["router"]
