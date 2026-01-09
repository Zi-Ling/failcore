# failcore/web/services/jobs_service.py
"""
Job management service.

Jobs represent background tasks (report generation, audit, replay, etc.)
All long-running operations go through the job queue.
"""

import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, List, Any
from failcore.utils.paths import get_failcore_root
from failcore.infra.storage.job import JobStorage


JobType = Literal["report", "audit", "replay", "run", "export"]
JobStatus = Literal["queued", "running", "success", "failed", "cancelled"]


@dataclass
class Job:
    """
    Represents a background task.
    
    Jobs unify all async operations (report, audit, replay, run)
    into a consistent execution model.
    """
    job_id: str
    type: JobType
    status: JobStatus
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    inputs: dict = None  # run_id, flags, params
    artifacts: List[dict] = None  # [{"path": ..., "type": ...}]
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class JobsService:
    """
    Job queue and execution manager with SQLite persistence.
    """
    
    def __init__(self):
        self._storage = JobStorage()
    
    def create_job(self, job_type: JobType, inputs: dict) -> Job:
        """Create a new job."""
        job_data = {
            "job_id": f"job_{uuid.uuid4().hex[:12]}",
            "type": job_type,
            "status": "queued",
            "created_at": time.time(),
            "inputs": inputs or {},
            "artifacts": [],
        }
        
        # Extract run_id from inputs if present (for easy querying)
        if inputs and "run_id" in inputs:
            job_data["run_id"] = inputs["run_id"]
        
        self._storage.create_job(job_data)
        
        # Convert to Job dataclass
        return Job(
            job_id=job_data["job_id"],
            type=job_data["type"],
            status=job_data["status"],
            created_at=job_data["created_at"],
            inputs=job_data["inputs"],
            artifacts=job_data["artifacts"],
        )
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        job_data = self._storage.get_job(job_id)
        if job_data:
            return self._dict_to_job(job_data)
        return None
    
    def list_jobs(
        self,
        limit: int = 50,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
    ) -> List[Job]:
        """List jobs with optional filtering."""
        job_dicts = self._storage.list_jobs(
            status=status,
            job_type=job_type,
            limit=limit,
            order_by="created_at",
            order_dir="DESC",
        )
        return [self._dict_to_job(jd) for jd in job_dicts]
    
    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
        artifacts: Optional[List[dict]] = None,
    ):
        """Update job status."""
        updates = {"status": status}
        
        if status == "running":
            updates["started_at"] = time.time()
        
        if status in ("success", "failed", "cancelled"):
            updates["finished_at"] = time.time()
            # Calculate duration if we have started_at
            job_data = self._storage.get_job(job_id)
            if job_data and job_data.get("started_at"):
                duration_ms = int((updates["finished_at"] - job_data["started_at"]) * 1000)
                updates["duration_ms"] = duration_ms
        
        if error:
            updates["error"] = error
        
        if artifacts is not None:
            updates["artifacts"] = artifacts
        
        self._storage.update_job(job_id, updates)
    
    def execute_job(self, job_id: str) -> bool:
        """
        Execute a job (synchronously for now).
        
        Future: enqueue to worker pool/celery/etc.
        """
        job = self.get_job(job_id)
        if not job:
            return False
        
        try:
            self.update_status(job_id, "running")
            
            # Dispatch to handler
            if job.type == "report":
                artifacts = self._execute_report(job)
            elif job.type == "audit":
                artifacts = self._execute_audit(job)
            elif job.type == "export":
                artifacts = self._execute_export(job)
            else:
                raise NotImplementedError(f"Job type {job.type} not implemented")
            
            self.update_status(job_id, "success", artifacts=artifacts)
            return True
        except Exception as e:
            self.update_status(job_id, "failed", error=str(e))
            return False
    
    def _dict_to_job(self, job_data: dict) -> Job:
        """Convert dictionary to Job dataclass."""
        return Job(
            job_id=job_data["job_id"],
            type=job_data["type"],
            status=job_data["status"],
            created_at=job_data["created_at"],
            started_at=job_data.get("started_at"),
            finished_at=job_data.get("finished_at"),
            inputs=job_data.get("inputs") or {},
            artifacts=job_data.get("artifacts") or [],
            error=job_data.get("error"),
        )
    
    def _execute_report(self, job: Job) -> List[dict]:
        """Execute report generation."""
        from failcore.cli.views.trace_report import build_report_view_from_trace
        from failcore.cli.renderers.html import HtmlRenderer
        from failcore.utils.paths import get_failcore_root
        from pathlib import Path
        
        run_id = job.inputs.get("run_id")
        if not run_id:
            raise ValueError("run_id required for report generation")
        
        # Parse run_id to find trace file: {date}_{run_name}
        parts = run_id.split("_", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid run_id format: {run_id}")
        
        date = parts[0]
        run_name = parts[1]
        
        # Find trace file
        run_dir = get_failcore_root() / "runs" / date / run_name
        trace_path = run_dir / "trace.jsonl"
        
        if not trace_path.exists():
            raise FileNotFoundError(f"Trace not found: {trace_path}")
        
        # Build view model from trace
        view = build_report_view_from_trace(Path(trace_path))
        
        # Render to HTML
        renderer = HtmlRenderer()
        html_content = renderer.render_trace_report(view)
        
        # Save report
        report_path = run_dir / "report.html"
        report_path.write_text(html_content, encoding='utf-8')
        
        # Use relative path from failcore root
        relative_path = report_path.relative_to(get_failcore_root())
        
        return [{
            "path": str(relative_path),
            "type": "report_html",
            "mime": "text/html",
        }]
    
    def _execute_audit(self, job: Job) -> List[dict]:
        """Execute audit generation."""
        from failcore.core.audit.analyzer import analyze_events
        from failcore.cli.views.audit_report import build_audit_view
        from failcore.cli.renderers.html import HtmlRenderer
        from failcore.utils.paths import get_failcore_root
        import json
        
        run_id = job.inputs.get("run_id")
        if not run_id:
            raise ValueError("run_id required for audit generation")
        
        # Parse run_id to find trace file
        parts = run_id.split("_", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid run_id format: {run_id}")
        
        date = parts[0]
        run_name = parts[1]
        
        # Find trace file
        run_dir = get_failcore_root() / "runs" / date / run_name
        trace_path = run_dir / "trace.jsonl"
        
        if not trace_path.exists():
            raise FileNotFoundError(f"Trace not found: {trace_path}")
        
        # Read trace events from JSONL file
        events = []
        with open(trace_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        
        # Analyze events to generate audit report
        report = analyze_events(events)
        
        # Save JSON audit
        audit_json_path = run_dir / "audit.json"
        audit_json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding='utf-8')
        
        # Build view and render HTML
        view = build_audit_view(report, trace_path=str(trace_path), trace_events=events)
        renderer = HtmlRenderer()
        html_content = renderer.render_audit_report(view)
        
        audit_html_path = run_dir / "audit.html"
        audit_html_path.write_text(html_content, encoding='utf-8')
        
        # Use relative paths from failcore root
        failcore_root = get_failcore_root()
        relative_json_path = audit_json_path.relative_to(failcore_root)
        relative_html_path = audit_html_path.relative_to(failcore_root)
        
        return [
            {
                "path": str(relative_json_path),
                "type": "audit_json",
                "mime": "application/json",
            },
            {
                "path": str(relative_html_path),
                "type": "audit_html",
                "mime": "text/html",
            }
        ]
    
    def _execute_export(self, job: Job) -> List[dict]:
        """Execute trace export."""
        from failcore.utils.paths import get_failcore_root
        
        run_id = job.inputs.get("run_id")
        if not run_id:
            raise ValueError("run_id required for export")
        
        # Parse run_id
        parts = run_id.split("_", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid run_id format: {run_id}")
        
        date = parts[0]
        run_name = parts[1]
        
        # Find trace file
        run_dir = get_failcore_root() / "runs" / date / run_name
        trace_path = run_dir / "trace.jsonl"
        
        if not trace_path.exists():
            raise FileNotFoundError(f"Trace not found: {trace_path}")
        
        # Use relative path from failcore root
        relative_path = trace_path.relative_to(get_failcore_root())
        
        return [{
            "path": str(relative_path),
            "type": "trace_export",
            "mime": "application/x-ndjson",
        }]


# Global singleton
_service = JobsService()


def get_jobs_service() -> JobsService:
    """Get the global jobs service."""
    return _service


__all__ = ["Job", "JobsService", "get_jobs_service", "JobType", "JobStatus"]
