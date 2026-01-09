# failcore/infra/storage/trace.py
"""
SQLite storage engine for trace events
"""

import sqlite3
import json
from typing import Any, Dict, List, Optional
from pathlib import Path


class SQLiteStore:
    """
    SQLite storage for trace events (v0.1.3)
    
    Three-table design:
    1. runs - run metadata with mode/session context
    2. events - unified event envelope (all event types)
    3. steps - aggregated step summary (materialized view for performance)
    """
    
    SCHEMA_VERSION = "0.1.3"
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
    
    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def init_schema(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()
        
        # Metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Runs table - track all runs with mode/session context (v0.1.3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                mode TEXT,
                session_id TEXT,
                parent_run_id TEXT,
                workspace TEXT,
                sandbox_root TEXT,
                trace_path TEXT,
                started_at TEXT,
                finished_at TEXT,
                status TEXT,
                client TEXT,
                tags TEXT,
                first_event_ts TEXT,
                last_event_ts TEXT,
                total_events INTEGER DEFAULT 0,
                total_steps INTEGER DEFAULT 0,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Events table - unified event envelope (v0.1.3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                ts TEXT NOT NULL,
                type TEXT NOT NULL,
                step_id TEXT,
                span_id TEXT,
                parent_span_id TEXT,
                severity TEXT DEFAULT 'info',
                fingerprint TEXT,
                source TEXT,
                payload_json TEXT NOT NULL,
                UNIQUE(run_id, seq),
                UNIQUE(event_id)
            )
        """)
        
        # Create indexes for events (v0.1.3 optimized)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_run_ts ON events(run_id, ts)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_run_type_ts ON events(run_id, type, ts)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_step_id ON events(step_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_fingerprint ON events(fingerprint)")
        
        # Steps table - aggregated step summary (v0.1.3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 1,
                start_seq INTEGER,
                end_seq INTEGER,
                started_at TEXT,
                finished_at TEXT,
                duration_ms INTEGER,
                status TEXT,
                error_code TEXT,
                error_message TEXT,
                fingerprint TEXT,
                http_status INTEGER,
                provider TEXT,
                model TEXT,
                payload_json TEXT,
                PRIMARY KEY (run_id, step_id, attempt)
            )
        """)
        
        # Create indexes for steps (v0.1.3 optimized)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_run_started ON steps(run_id, started_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_run_status ON steps(run_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_kind ON steps(kind)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_fingerprint ON steps(fingerprint)")
        
        # Create indexes for runs (v0.1.3 optimized)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_mode_created ON runs(mode, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_session_id ON runs(session_id)")
        
        # Store schema version
        cursor.execute("""
            INSERT OR REPLACE INTO _metadata (key, value)
            VALUES ('schema_version', ?)
        """, (self.SCHEMA_VERSION,))
        
        self.conn.commit()
    
    def upsert_run(self, run_id: str, run_data: Dict[str, Any]):
        """Insert or update run metadata (v0.1.3)"""
        cursor = self.conn.cursor()
        
        # Serialize tags as JSON if present
        tags = run_data.get("tags")
        if tags and not isinstance(tags, str):
            tags = json.dumps(tags)
        
        cursor.execute("""
            INSERT OR REPLACE INTO runs 
            (run_id, created_at, mode, session_id, parent_run_id, workspace, sandbox_root, 
             trace_path, started_at, finished_at, status, client, tags, 
             first_event_ts, last_event_ts, total_events, total_steps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            run_data.get("created_at"),
            run_data.get("mode"),
            run_data.get("session_id"),
            run_data.get("parent_run_id"),
            run_data.get("workspace"),
            run_data.get("sandbox_root"),
            run_data.get("trace_path"),
            run_data.get("started_at"),
            run_data.get("finished_at"),
            run_data.get("status"),
            run_data.get("client"),
            tags,
            run_data.get("first_event_ts"),
            run_data.get("last_event_ts"),
            run_data.get("total_events", 0),
            run_data.get("total_steps", 0),
        ))
        self.conn.commit()
    
    def insert_event(self, event: Dict[str, Any]):
        """Insert raw event (v0.1.3 envelope)"""
        cursor = self.conn.cursor()
        
        # Extract envelope fields
        run_id = event.get("run", {}).get("run_id", "unknown")
        seq = event.get("seq", 0)
        ts = event.get("ts", "")
        
        evt = event.get("event", {})
        evt_type = evt.get("type", "UNKNOWN")
        
        # Extract data fields (unified structure)
        data = evt.get("data", {})
        step_id = data.get("step_id")
        fingerprint = data.get("fingerprint")
        
        # Generate event_id if not present
        event_id = event.get("event_id")
        if not event_id:
            import uuid
            event_id = f"{run_id}:{seq}:{uuid.uuid4().hex[:8]}"
        
        # Optional fields
        span_id = data.get("span_id")
        parent_span_id = data.get("parent_span_id")
        severity = event.get("severity", "info")
        source = event.get("source") or event.get("run", {}).get("kind")
        
        # Store full event as payload_json
        payload_json = json.dumps(event)
        
        cursor.execute("""
            INSERT OR IGNORE INTO events
            (event_id, run_id, seq, ts, type, step_id, span_id, parent_span_id, 
             severity, fingerprint, source, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, run_id, seq, ts, evt_type, step_id, span_id, parent_span_id,
              severity, fingerprint, source, payload_json))
    
    def upsert_step(self, step_data: Dict[str, Any]):
        """Insert or update step aggregation (v0.1.3)"""
        cursor = self.conn.cursor()
        
        # Serialize payload_json if present and not a string
        if "payload_json" in step_data and not isinstance(step_data["payload_json"], str):
            step_data["payload_json"] = json.dumps(step_data["payload_json"])
        
        # Check if step exists
        cursor.execute("""
            SELECT 1 FROM steps
            WHERE run_id = ? AND step_id = ? AND attempt = ?
        """, (step_data["run_id"], step_data["step_id"], step_data.get("attempt", 1)))
        
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update existing
            set_parts = []
            values = []
            for key, value in step_data.items():
                if key not in ("run_id", "step_id", "attempt"):
                    set_parts.append(f"{key} = ?")
                    values.append(value)
            
            values.extend([step_data["run_id"], step_data["step_id"], step_data.get("attempt", 1)])
            
            cursor.execute(f"""
                UPDATE steps
                SET {", ".join(set_parts)}
                WHERE run_id = ? AND step_id = ? AND attempt = ?
            """, values)
        else:
            # Insert new
            keys = list(step_data.keys())
            placeholders = ", ".join(["?"] * len(keys))
            cursor.execute(f"""
                INSERT INTO steps ({", ".join(keys)})
                VALUES ({placeholders})
            """, [step_data[k] for k in keys])
    
    def query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute SQL query"""
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_stats(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Get database statistics, optionally filtered by run_id"""
        cursor = self.conn.cursor()
        
        where_clause = f"WHERE run_id = '{run_id}'" if run_id else ""
        
        # Count events
        cursor.execute(f"SELECT COUNT(*) as count FROM events {where_clause}")
        event_count = cursor.fetchone()["count"]
        
        # Count steps
        cursor.execute(f"SELECT COUNT(*) as count FROM steps {where_clause}")
        step_count = cursor.fetchone()["count"]
        
        # Count runs
        if run_id:
            run_count = 1
        else:
            cursor.execute("SELECT COUNT(*) as count FROM runs")
            run_count = cursor.fetchone()["count"]
        
        # Status distribution
        cursor.execute(f"""
            SELECT status, COUNT(*) as count 
            FROM steps 
            WHERE status IS NOT NULL {f"AND run_id = '{run_id}'" if run_id else ""}
            GROUP BY status
            ORDER BY count DESC
        """)
        status_dist = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # Kind distribution (v0.1.3)
        cursor.execute(f"""
            SELECT kind, COUNT(*) as count
            FROM steps
            {where_clause}
            GROUP BY kind
            ORDER BY count DESC
            LIMIT 10
        """)
        kind_dist = {row["kind"]: row["count"] for row in cursor.fetchall()}
        
        # Name distribution (top 10 step names)
        cursor.execute(f"""
            SELECT name, COUNT(*) as count
            FROM steps
            {where_clause}
            GROUP BY name
            ORDER BY count DESC
            LIMIT 10
        """)
        name_dist = {row["name"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "events": event_count,
            "steps": step_count,
            "runs": run_count,
            "status_distribution": status_dist,
            "kind_distribution": kind_dist,
            "name_distribution": name_dist,
        }
    
    def commit(self):
        """Commit transaction"""
        if self.conn:
            self.conn.commit()
