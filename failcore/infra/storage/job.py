# failcore/infra/storage/job.py
"""
SQLite storage for background jobs
"""

import sqlite3
import json
import time
from typing import Any, Dict, List, Optional
from pathlib import Path


class JobStorage:
    """
    SQLite storage for background jobs
    
    Table design:
    - jobs: Job metadata and state (with extensible fields for future features)
    """
    
    SCHEMA_VERSION = "0.1.0"
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Args:
            db_path: Optional custom SQLite database path.
                     If None, uses unified failcore.db from get_database_path()
        """
        if db_path is None:
            from ...utils.paths import get_database_path
            self.db_path = get_database_path()
        else:
            self.db_path = Path(db_path)
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema
        self._init_schema()
    
    def _init_schema(self):
        """Initialize jobs table schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Jobs table - background task tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    -- Identity
                    job_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    
                    -- State
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL,
                    updated_at REAL,
                    
                    -- Execution context
                    inputs TEXT,
                    artifacts TEXT,
                    error TEXT,
                    
                    -- Extended fields (for future features)
                    priority INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 0,
                    worker_id TEXT,
                    parent_job_id TEXT,
                    run_id TEXT,
                    user_id TEXT,
                    org_id TEXT,
                    tags TEXT,
                    metadata TEXT,
                    
                    -- Performance tracking
                    duration_ms INTEGER,
                    cpu_time_ms INTEGER,
                    memory_peak_mb INTEGER,
                    
                    -- Scheduling
                    scheduled_at REAL,
                    timeout_seconds INTEGER,
                    expires_at REAL
                )
            """)
            
            # Create indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_run_id ON jobs(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs(status, priority DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_parent_job_id ON jobs(parent_job_id)")
            
            # Store schema version
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _job_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO _job_metadata (key, value)
                VALUES ('schema_version', ?)
            """, (self.SCHEMA_VERSION,))
            
            conn.commit()
    
    def create_job(self, job_data: Dict[str, Any]) -> str:
        """
        Create a new job
        
        Args:
            job_data: Job data dictionary
        
        Returns:
            job_id of created job
        """
        with sqlite3.connect(self.db_path) as conn:
            # Serialize JSON fields
            inputs = job_data.get("inputs")
            if inputs and not isinstance(inputs, str):
                inputs = json.dumps(inputs)
            
            artifacts = job_data.get("artifacts", [])
            if not isinstance(artifacts, str):
                artifacts = json.dumps(artifacts)
            
            tags = job_data.get("tags")
            if tags and not isinstance(tags, str):
                tags = json.dumps(tags)
            
            metadata = job_data.get("metadata")
            if metadata and not isinstance(metadata, str):
                metadata = json.dumps(metadata)
            
            # Set updated_at to created_at initially
            updated_at = job_data.get("created_at", time.time())
            
            conn.execute("""
                INSERT INTO jobs 
                (job_id, type, status, created_at, started_at, finished_at, updated_at,
                 inputs, artifacts, error, priority, retry_count, max_retries, 
                 worker_id, parent_job_id, run_id, user_id, org_id, tags, metadata,
                 duration_ms, cpu_time_ms, memory_peak_mb, 
                 scheduled_at, timeout_seconds, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_data["job_id"],
                job_data["type"],
                job_data["status"],
                job_data["created_at"],
                job_data.get("started_at"),
                job_data.get("finished_at"),
                updated_at,
                inputs,
                artifacts,
                job_data.get("error"),
                job_data.get("priority", 0),
                job_data.get("retry_count", 0),
                job_data.get("max_retries", 0),
                job_data.get("worker_id"),
                job_data.get("parent_job_id"),
                job_data.get("run_id"),
                job_data.get("user_id"),
                job_data.get("org_id"),
                tags,
                metadata,
                job_data.get("duration_ms"),
                job_data.get("cpu_time_ms"),
                job_data.get("memory_peak_mb"),
                job_data.get("scheduled_at"),
                job_data.get("timeout_seconds"),
                job_data.get("expires_at"),
            ))
            conn.commit()
            
        return job_data["job_id"]
    
    def update_job(self, job_id: str, updates: Dict[str, Any]):
        """
        Update a job
        
        Args:
            job_id: Job ID to update
            updates: Dictionary of fields to update
        """
        with sqlite3.connect(self.db_path) as conn:
            # Serialize JSON fields if present
            if "inputs" in updates and not isinstance(updates["inputs"], str):
                updates["inputs"] = json.dumps(updates["inputs"])
            
            if "artifacts" in updates and not isinstance(updates["artifacts"], str):
                updates["artifacts"] = json.dumps(updates["artifacts"])
            
            if "tags" in updates and not isinstance(updates["tags"], str):
                updates["tags"] = json.dumps(updates["tags"])
            
            if "metadata" in updates and not isinstance(updates["metadata"], str):
                updates["metadata"] = json.dumps(updates["metadata"])
            
            # Always update updated_at
            updates["updated_at"] = time.time()
            
            # Build SET clause
            set_parts = []
            values = []
            for key, value in updates.items():
                set_parts.append(f"{key} = ?")
                values.append(value)
            
            values.append(job_id)
            
            conn.execute(f"""
                UPDATE jobs
                SET {", ".join(set_parts)}
                WHERE job_id = ?
            """, values)
            conn.commit()
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a job by ID
        
        Args:
            job_id: Job ID
        
        Returns:
            Job data dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM jobs WHERE job_id = ?
            """, (job_id,))
            row = cursor.fetchone()
            
            if row:
                return self._deserialize_job(dict(row))
            return None
    
    def list_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        run_id: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_dir: str = "DESC",
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional filtering
        
        Args:
            status: Filter by status
            job_type: Filter by type
            run_id: Filter by run_id
            parent_job_id: Filter by parent_job_id
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            order_by: Column to order by
            order_dir: Order direction (ASC/DESC)
        
        Returns:
            List of job dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Build WHERE clause
            where_parts = []
            params = []
            
            if status:
                where_parts.append("status = ?")
                params.append(status)
            
            if job_type:
                where_parts.append("type = ?")
                params.append(job_type)
            
            if run_id:
                where_parts.append("run_id = ?")
                params.append(run_id)
            
            if parent_job_id:
                where_parts.append("parent_job_id = ?")
                params.append(parent_job_id)
            
            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            
            # Validate order_by and order_dir
            allowed_columns = [
                "created_at", "started_at", "finished_at", "updated_at",
                "status", "type", "priority", "duration_ms"
            ]
            if order_by not in allowed_columns:
                order_by = "created_at"
            
            if order_dir.upper() not in ("ASC", "DESC"):
                order_dir = "DESC"
            
            params.extend([limit, offset])
            
            cursor = conn.execute(f"""
                SELECT * FROM jobs
                {where_clause}
                ORDER BY {order_by} {order_dir}
                LIMIT ? OFFSET ?
            """, params)
            
            rows = cursor.fetchall()
            return [self._deserialize_job(dict(row)) for row in rows]
    
    def count_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """
        Count jobs with optional filtering
        
        Args:
            status: Filter by status
            job_type: Filter by type
            run_id: Filter by run_id
        
        Returns:
            Number of jobs matching criteria
        """
        with sqlite3.connect(self.db_path) as conn:
            where_parts = []
            params = []
            
            if status:
                where_parts.append("status = ?")
                params.append(status)
            
            if job_type:
                where_parts.append("type = ?")
                params.append(job_type)
            
            if run_id:
                where_parts.append("run_id = ?")
                params.append(run_id)
            
            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            
            cursor = conn.execute(f"""
                SELECT COUNT(*) as count FROM jobs
                {where_clause}
            """, params)
            
            return cursor.fetchone()[0]
    
    def delete_job(self, job_id: str):
        """
        Delete a job
        
        Args:
            job_id: Job ID to delete
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
    
    def cleanup_old_jobs(self, older_than_days: int = 30):
        """
        Clean up old completed/failed jobs
        
        Args:
            older_than_days: Delete jobs older than this many days
        """
        cutoff = time.time() - (older_than_days * 24 * 60 * 60)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM jobs
                WHERE status IN ('success', 'failed', 'cancelled')
                  AND finished_at < ?
            """, (cutoff,))
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get job statistics
        
        Returns:
            Dictionary with job statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Total count
            cursor = conn.execute("SELECT COUNT(*) as count FROM jobs")
            total = cursor.fetchone()["count"]
            
            # Status distribution
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM jobs
                GROUP BY status
                ORDER BY count DESC
            """)
            status_dist = {row["status"]: row["count"] for row in cursor.fetchall()}
            
            # Type distribution
            cursor = conn.execute("""
                SELECT type, COUNT(*) as count
                FROM jobs
                GROUP BY type
                ORDER BY count DESC
            """)
            type_dist = {row["type"]: row["count"] for row in cursor.fetchall()}
            
            # Average duration by type
            cursor = conn.execute("""
                SELECT type, AVG(duration_ms) as avg_duration
                FROM jobs
                WHERE duration_ms IS NOT NULL
                GROUP BY type
            """)
            avg_duration = {row["type"]: row["avg_duration"] for row in cursor.fetchall()}
            
            return {
                "total": total,
                "status_distribution": status_dist,
                "type_distribution": type_dist,
                "avg_duration_ms": avg_duration,
            }
    
    def _deserialize_job(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize JSON fields in job row
        
        Args:
            row: Raw database row
        
        Returns:
            Deserialized job dictionary
        """
        # Deserialize JSON fields
        if row.get("inputs"):
            try:
                row["inputs"] = json.loads(row["inputs"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        if row.get("artifacts"):
            try:
                row["artifacts"] = json.loads(row["artifacts"])
            except (json.JSONDecodeError, TypeError):
                row["artifacts"] = []
        
        if row.get("tags"):
            try:
                row["tags"] = json.loads(row["tags"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        if row.get("metadata"):
            try:
                row["metadata"] = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        return row
