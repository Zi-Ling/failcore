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
    Job queue and execution manager.
    
    Currently in-memory (simple). Future: Redis/SQLite for persistence.
    """
    
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._jobs_dir = get_failcore_root() / "jobs"
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._load_persisted_jobs()
    
    def _load_persisted_jobs(self):
        """Load jobs from disk (simple persistence)."""
        jobs_index = self._jobs_dir / "jobs.jsonl"
        if jobs_index.exists():
            try:
                with open(jobs_index, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            job_data = json.loads(line)
                            job = Job(**job_data)
                            self._jobs[job.job_id] = job
            except Exception:
                pass  # Ignore corrupted job index
    
    def _persist_job(self, job: Job):
        """Persist job to disk."""
        jobs_index = self._jobs_dir / "jobs.jsonl"
        with open(jobs_index, 'a', encoding='utf-8') as f:
            f.write(json.dumps(job.to_dict()) + "\n")
    
    def create_job(self, job_type: JobType, inputs: dict) -> Job:
        """Create a new job."""
        job = Job(
            job_id=f"job_{uuid.uuid4().hex[:12]}",
            type=job_type,
            status="queued",
            created_at=time.time(),
            inputs=inputs or {},
            artifacts=[],
        )
        self._jobs[job.job_id] = job
        self._persist_job(job)
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self._jobs.get(job_id)
    
    def list_jobs(
        self,
        limit: int = 50,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
    ) -> List[Job]:
        """List jobs with optional filtering."""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.type == job_type]
        
        # Sort by created_at (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]
    
    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
        artifacts: Optional[List[dict]] = None,
    ):
        """Update job status."""
        job = self._jobs.get(job_id)
        if not job:
            return
        
        job.status = status
        if status == "running" and job.started_at is None:
            job.started_at = time.time()
        if status in ("success", "failed", "cancelled"):
            job.finished_at = time.time()
        if error:
            job.error = error
        if artifacts:
            job.artifacts = artifacts
        
        self._persist_job(job)
    
    def execute_job(self, job_id: str) -> bool:
        """
        Execute a job (synchronously for now).
        
        Future: enqueue to worker pool/celery/etc.
        """
        job = self._jobs.get(job_id)
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
    
    def _execute_report(self, job: Job) -> List[dict]:
        """Execute report generation."""
        from failcore.cli.renderers.html.report import render_report_html
        from failcore.infra.storage.trace_reader import JsonlTraceReader
        from failcore.utils.paths import get_failcore_root
        import json
        
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
        
        # Read trace
        reader = JsonlTraceReader(str(trace_path))
        events = list(reader.read_events())
        
        # Generate HTML report
        html_content = render_report_html(events)
        
        # Save report
        report_path = run_dir / "report.html"
        report_path.write_text(html_content, encoding='utf-8')
        
        return [{
            "path": str(report_path),
            "type": "report_html",
            "mime": "text/html",
        }]
    
    def _execute_audit(self, job: Job) -> List[dict]:
        """Execute audit generation."""
        from failcore.core.audit.analyzer import AuditAnalyzer
        from failcore.infra.storage.trace_reader import JsonlTraceReader
        from failcore.cli.renderers.html.sections.audit_report import render_audit_section
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
        
        # Read trace and analyze
        reader = JsonlTraceReader(str(trace_path))
        events = list(reader.read_events())
        
        analyzer = AuditAnalyzer()
        report = analyzer.analyze(events)
        
        # Save JSON audit
        audit_json_path = run_dir / "audit.json"
        audit_json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding='utf-8')
        
        # Generate HTML audit report
        html_content = render_audit_section(report)
        audit_html_path = run_dir / "audit_report.html"
        audit_html_path.write_text(html_content, encoding='utf-8')
        
        return [
            {
                "path": str(audit_json_path),
                "type": "audit_json",
                "mime": "application/json",
            },
            {
                "path": str(audit_html_path),
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
        
        return [{
            "path": str(trace_path),
            "type": "trace_export",
            "mime": "application/x-ndjson",
        }]


# Global singleton
_service = JobsService()


def get_jobs_service() -> JobsService:
    """Get the global jobs service."""
    return _service


__all__ = ["Job", "JobsService", "get_jobs_service", "JobType", "JobStatus"]
