"""
Cost Storage Tables

SQLite table definitions:
- runs: Run-level aggregation (SHARED with trace.py)
  - Base columns: run_id, created_at, workspace, trace_path, etc. (trace.py schema)
  - Cost columns: total_cost_usd, total_tokens, blocked_reason, etc. (CostStorage additions)
  - Design: CostStorage creates full table if not exists, then adds cost columns
  
- usage: Step-level detailed records (incremental, cumulative, time series)
  - Fully managed by CostStorage
  - One row per step execution

Initialization Strategy:
1. CostStorage creates base runs table (if not exists) using sqlite_store schema
2. CostStorage adds cost-specific columns via ALTER TABLE
3. Both modules can safely use CREATE TABLE IF NOT EXISTS (idempotent)
4. Cost columns are added on first CostStorage initialization
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import sqlite3
import json
from datetime import datetime


class CostStorage:
    """
    Cost data storage
    
    Two tables:
    - runs: One row per run (aggregated data, fast queries)
    - usage: One row per step (detailed data, for curves)
    
    Database Location:
    - Uses unified .failcore/failcore.db (same as other FailCore data)
    - Path determined by failcore.utils.paths.get_database_path()
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Args:
            db_path: Optional custom SQLite database path.
                     If None, uses get_database_path() for unified storage.
        """
        if db_path is None:
            from ...utils.paths import get_database_path
            self.db_path = get_database_path()
        else:
            self.db_path = Path(db_path)
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
    
    def _init_tables(self):
        """
        Initialize cost tracking tables.
        
        Strategy:
        1. Ensure base runs table exists (create if needed with sqlite_store schema)
        2. ADD cost columns to runs table
        3. Create usage table for step-level details
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if runs table exists
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
            runs_exists = cursor.fetchone() is not None
            
            if not runs_exists:
                # Create base runs table using sqlite_store schema
                # This ensures compatibility with trace ingest
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        workspace TEXT,
                        sandbox_root TEXT,
                        trace_path TEXT,
                        first_event_ts TEXT,
                        last_event_ts TEXT,
                        total_events INTEGER DEFAULT 0,
                        total_steps INTEGER DEFAULT 0,
                        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            # Get existing columns
            cursor = conn.execute("PRAGMA table_info(runs)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            
            # Migration: Add cost-tracking columns to runs table
            # SQLite ALTER TABLE only supports constant defaults (no CURRENT_TIMESTAMP)
            cost_columns = [
                ("total_cost_usd", "REAL", "0.0"),
                ("total_tokens", "INTEGER", "0"),
                ("total_api_calls", "INTEGER", "0"),
                ("blocked_step_id", "TEXT", "NULL"),
                ("blocked_reason", "TEXT", "NULL"),
                ("blocked_error_code", "TEXT", "NULL"),
                ("last_step_seq", "INTEGER", "0"),
                ("run_status", "TEXT", "'running'"),
                ("run_updated_at", "TEXT", "NULL"),
            ]
            
            for col_name, col_type, default_val in cost_columns:
                if col_name not in existing_cols:
                    try:
                        conn.execute(f"ALTER TABLE runs ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" not in str(e).lower():
                            raise
            # and we'll add columns on next init
            
            # usage table: step-level detailed records
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    tool TEXT NOT NULL,
                    
                    -- Incremental cost (this step)
                    delta_cost_usd REAL NOT NULL,
                    delta_tokens INTEGER NOT NULL,
                    delta_input_tokens INTEGER NOT NULL DEFAULT 0,
                    delta_output_tokens INTEGER NOT NULL DEFAULT 0,
                    delta_api_calls INTEGER NOT NULL DEFAULT 1,
                    
                    -- Cumulative cost (up to this step)
                    cumulative_cost_usd REAL NOT NULL,
                    cumulative_tokens INTEGER NOT NULL,
                    cumulative_api_calls INTEGER NOT NULL,
                    
                    -- Metadata
                    status TEXT NOT NULL,
                    error_code TEXT,
                    estimated BOOLEAN NOT NULL DEFAULT 1,
                    model TEXT,
                    provider TEXT,
                    
                    -- Timing
                    ts TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    
                    -- Index constraint
                    UNIQUE(run_id, step_id, seq)
                )
            """)
            
            # Create indexes for usage
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_run_id ON usage(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_run_seq ON usage(run_id, seq)")
            
            # budget table: Budget snapshots for audit & replay
            # Facts (usage/cost) live in `usage` + `runs`.
            # This table stores "what limits applied" for audit/replay purposes.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budget (
                    -- Identity
                    budget_id TEXT PRIMARY KEY,
                    
                    -- Scope + targeting
                    scope TEXT NOT NULL,
                    run_id TEXT,
                    user_id TEXT,
                    org_id TEXT,
                    
                    -- Constraints (limits)
                    max_cost_usd REAL,
                    max_tokens INTEGER,
                    max_api_calls INTEGER,
                    max_usd_per_minute REAL,
                    
                    -- Optional counters snapshot (NOT source of truth; derived from usage if needed)
                    used_cost_usd REAL NOT NULL DEFAULT 0.0,
                    used_tokens INTEGER NOT NULL DEFAULT 0,
                    used_api_calls INTEGER NOT NULL DEFAULT 0,
                    
                    -- Metadata timestamps (ISO8601 UTC strings)
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    
                    -- Basic sanity checks
                    CHECK (scope IN ('run','day','month','user','org')),
                    CHECK (max_cost_usd IS NULL OR max_cost_usd >= 0),
                    CHECK (max_tokens IS NULL OR max_tokens >= 0),
                    CHECK (max_api_calls IS NULL OR max_api_calls >= 0),
                    CHECK (max_usd_per_minute IS NULL OR max_usd_per_minute >= 0),
                    CHECK (used_cost_usd >= 0),
                    CHECK (used_tokens >= 0),
                    CHECK (used_api_calls >= 0),
                    
                    -- Scope/target contract checks
                    CHECK (scope != 'run' OR run_id IS NOT NULL),
                    CHECK (scope NOT IN ('user','day','month') OR user_id IS NOT NULL),
                    CHECK (scope != 'org' OR org_id IS NOT NULL)
                )
            """)
            
            # Helpful indexes for budget lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_run_id ON budget(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_user_id ON budget(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_org_id ON budget(org_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_scope ON budget(scope)")
            
            conn.commit()
    
    def upsert_run(
        self,
        run_id: str,
        created_at: Optional[str] = None,
        total_cost_usd: Optional[float] = None,
        total_tokens: Optional[int] = None,
        total_api_calls: Optional[int] = None,
        total_steps: Optional[int] = None,
        blocked_step_id: Optional[str] = None,
        blocked_reason: Optional[str] = None,
        blocked_error_code: Optional[str] = None,
        last_step_seq: Optional[int] = None,
        status: Optional[str] = None,
    ):
        """
        Upsert cost tracking data for a run (INSERT or UPDATE)
        
        Design: This method ensures cost data can be written immediately during execution.
        - If run exists: UPDATE cost columns
        - If run doesn't exist: INSERT basic record with cost data
        - Trace ingest (trace.py) can later enrich with workspace/trace_path
        
        Args:
            run_id: Run ID
            created_at: Creation time (for INSERT)
            total_cost_usd: Total cost
            total_tokens: Total tokens
            total_api_calls: Total API calls
            total_steps: Total steps
            blocked_step_id: ID of blocked step
            blocked_reason: Reason for blocking
            blocked_error_code: Error code
            last_step_seq: Last step sequence number
            status: Status (running/completed/blocked)
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if exists
            cursor = conn.execute("SELECT run_id FROM runs WHERE run_id = ?", (run_id,))
            exists = cursor.fetchone() is not None
            
            now = datetime.utcnow().isoformat()
            
            if exists:
                # Update
                updates = []
                params = []
                
                if total_cost_usd is not None:
                    updates.append("total_cost_usd = ?")
                    params.append(total_cost_usd)
                if total_tokens is not None:
                    updates.append("total_tokens = ?")
                    params.append(total_tokens)
                if total_api_calls is not None:
                    updates.append("total_api_calls = ?")
                    params.append(total_api_calls)
                if total_steps is not None:
                    updates.append("total_steps = ?")
                    params.append(total_steps)
                if blocked_step_id is not None:
                    updates.append("blocked_step_id = ?")
                    params.append(blocked_step_id)
                if blocked_reason is not None:
                    updates.append("blocked_reason = ?")
                    params.append(blocked_reason)
                if blocked_error_code is not None:
                    updates.append("blocked_error_code = ?")
                    params.append(blocked_error_code)
                if last_step_seq is not None:
                    updates.append("last_step_seq = ?")
                    params.append(last_step_seq)
                if status is not None:
                    updates.append("run_status = ?")
                    params.append(status)
                
                updates.append("run_updated_at = ?")
                params.append(now)
                params.append(run_id)
                
                sql = f"UPDATE runs SET {', '.join(updates)} WHERE run_id = ?"
                conn.execute(sql, params)
            else:
                # INSERT basic run record if doesn't exist
                # This ensures cost data can be written even if trace hasn't been ingested yet
                conn.execute("""
                    INSERT INTO runs (
                        run_id, created_at, 
                        total_cost_usd, total_tokens, total_api_calls,
                        blocked_step_id, blocked_reason, blocked_error_code,
                        last_step_seq, run_status, run_updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    created_at or now,
                    total_cost_usd or 0.0,
                    total_tokens or 0,
                    total_api_calls or 0,
                    blocked_step_id,
                    blocked_reason,
                    blocked_error_code,
                    last_step_seq or 0,
                    status or "running",
                    now,
                ))
            
            conn.commit()
    
    def insert_usage(
        self,
        run_id: str,
        step_id: str,
        seq: int,
        tool: str,
        delta_cost_usd: float,
        delta_tokens: int,
        cumulative_cost_usd: float,
        cumulative_tokens: int,
        cumulative_api_calls: int,
        status: str,
        ts: str,
        delta_input_tokens: int = 0,
        delta_output_tokens: int = 0,
        delta_api_calls: int = 1,
        error_code: Optional[str] = None,
        estimated: bool = True,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        duration_ms: int = 0,
    ):
        """
        Insert usage record
        
        Args:
            run_id: Run ID
            step_id: Step ID
            seq: Sequence number
            tool: Tool name
            delta_cost_usd: Incremental cost
            delta_tokens: Incremental tokens
            cumulative_cost_usd: Cumulative cost
            cumulative_tokens: Cumulative tokens
            cumulative_api_calls: Cumulative API calls
            status: Status
            ts: Timestamp
            delta_input_tokens: Incremental input tokens
            delta_output_tokens: Incremental output tokens
            delta_api_calls: Incremental API calls
            error_code: Error code
            estimated: Whether estimated
            model: Model name
            provider: Provider name
            duration_ms: Duration in milliseconds
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO usage (
                    run_id, step_id, seq, tool,
                    delta_cost_usd, delta_tokens, delta_input_tokens, delta_output_tokens, delta_api_calls,
                    cumulative_cost_usd, cumulative_tokens, cumulative_api_calls,
                    status, error_code, estimated, model, provider,
                    ts, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, step_id, seq, tool,
                delta_cost_usd, delta_tokens, delta_input_tokens, delta_output_tokens, delta_api_calls,
                cumulative_cost_usd, cumulative_tokens, cumulative_api_calls,
                status, error_code, 1 if estimated else 0, model, provider,
                ts, duration_ms,
            ))
            conn.commit()
    
    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run summary"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_run_curve(self, run_id: str) -> List[Dict[str, Any]]:
        """Get run cost curve (all usage records)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM usage 
                WHERE run_id = ? 
                ORDER BY seq
            """, (run_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def list_runs(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "updated_at DESC",
    ) -> List[Dict[str, Any]]:
        """List all runs"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"""
                SELECT * FROM runs 
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
            """, (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    # ---- Budget Management (Audit & Replay) ----
    
    def insert_budget_snapshot(
        self,
        budget_id: str,
        scope: str,
        max_cost_usd: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_api_calls: Optional[int] = None,
        max_usd_per_minute: Optional[float] = None,
        run_id: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ):
        """
        Insert budget snapshot for audit/replay purposes
        
        This records "what limits were applied" at the start of a run/scope.
        NOT used for real-time enforcement (CostGuardian handles that).
        
        Args:
            budget_id: Unique budget identifier (e.g., f"run_{run_id}")
            scope: Budget scope ('run', 'day', 'month', 'user', 'org')
            max_cost_usd: Maximum cost limit
            max_tokens: Maximum tokens limit
            max_api_calls: Maximum API calls limit
            max_usd_per_minute: Burn rate limit
            run_id: Run ID (required if scope='run')
            user_id: User ID (required if scope in ['user', 'day', 'month'])
            org_id: Org ID (required if scope='org')
        """
        from datetime import datetime
        
        now = datetime.utcnow().isoformat()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO budget (
                        budget_id, scope, run_id, user_id, org_id,
                        max_cost_usd, max_tokens, max_api_calls, max_usd_per_minute,
                        used_cost_usd, used_tokens, used_api_calls,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, 0, ?, ?)
                """, (
                    budget_id, scope, run_id, user_id, org_id,
                    max_cost_usd, max_tokens, max_api_calls, max_usd_per_minute,
                    now, now
                ))
                conn.commit()
        except sqlite3.IntegrityError:
            # Budget already exists (duplicate run), ignore
            pass
        except sqlite3.Error:
            # Silently fail if table doesn't exist or constraints violated
            pass
    
    def get_budget_snapshot(self, budget_id: str) -> Optional[Dict[str, Any]]:
        """Get budget snapshot by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM budget WHERE budget_id = ?", (budget_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error:
            return None
    
    def get_budget_for_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get budget snapshot for a specific run"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM budget WHERE run_id = ? AND scope = 'run'", (run_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error:
            return None
    
    def list_budgets(
        self,
        scope: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List budget snapshots"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if scope:
                    cursor = conn.execute("""
                        SELECT * FROM budget 
                        WHERE scope = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (scope, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM budget 
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []


__all__ = ["CostStorage"]
