# failcore/infra/storage/sqlite_store.py
"""
SQLite storage engine for trace events
"""

import sqlite3
import json
from typing import Any, Dict, List, Optional
from pathlib import Path


class SQLiteStore:
    """
    SQLite storage for trace events
    
    Two-table design:
    1. events - raw events (source of truth)
    2. steps - aggregated step lifecycle (query-optimized)
    """
    
    SCHEMA_VERSION = "0.1.1"
    
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
        
        # Runs table - track all runs
        cursor.execute("""
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
        
        # Events table - raw events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                type TEXT NOT NULL,
                step_id TEXT,
                tool TEXT,
                attempt INTEGER,
                json TEXT NOT NULL,
                UNIQUE(run_id, seq)
            )
        """)
        
        # Create indexes for events
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_step_id ON events(step_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_tool ON events(tool)")
        
        # Steps table - aggregated view
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 1,
                start_seq INTEGER,
                end_seq INTEGER,
                start_ts TEXT,
                end_ts TEXT,
                status TEXT,
                phase TEXT,
                duration_ms INTEGER,
                warnings TEXT,
                fingerprint_id TEXT,
                error_code TEXT,
                error_message TEXT,
                has_policy_denied INTEGER DEFAULT 0,
                has_output_normalized INTEGER DEFAULT 0,
                PRIMARY KEY (run_id, step_id, attempt)
            )
        """)
        
        # Create indexes for steps
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_tool ON steps(tool)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_status ON steps(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_phase ON steps(phase)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_run_id ON steps(run_id)")
        
        # Create index for runs
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at)")
        
        # Store schema version
        cursor.execute("""
            INSERT OR REPLACE INTO _metadata (key, value)
            VALUES ('schema_version', ?)
        """, (self.SCHEMA_VERSION,))
        
        self.conn.commit()
    
    def upsert_run(self, run_id: str, run_data: Dict[str, Any]):
        """Insert or update run metadata"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO runs 
            (run_id, created_at, workspace, sandbox_root, trace_path, 
             first_event_ts, last_event_ts, total_events, total_steps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            run_data.get("created_at"),
            run_data.get("workspace"),
            run_data.get("sandbox_root"),
            run_data.get("trace_path"),
            run_data.get("first_event_ts"),
            run_data.get("last_event_ts"),
            run_data.get("total_events", 0),
            run_data.get("total_steps", 0),
        ))
        self.conn.commit()
    
    def insert_event(self, event: Dict[str, Any]):
        """Insert raw event"""
        cursor = self.conn.cursor()
        
        # Extract key fields
        run_id = event.get("run", {}).get("run_id", "unknown")
        seq = event.get("seq", 0)
        ts = event.get("ts", "")
        level = event.get("level", "INFO")
        
        evt = event.get("event", {})
        evt_type = evt.get("type", "UNKNOWN")
        
        step = evt.get("step", {})
        step_id = step.get("id")
        tool = step.get("tool")
        attempt = step.get("attempt", 1)
        
        # Store full JSON
        json_str = json.dumps(event)
        
        cursor.execute("""
            INSERT OR IGNORE INTO events
            (run_id, seq, ts, level, type, step_id, tool, attempt, json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (run_id, seq, ts, level, evt_type, step_id, tool, attempt, json_str))
    
    def upsert_step(self, step_data: Dict[str, Any]):
        """Insert or update step aggregation"""
        cursor = self.conn.cursor()
        
        # Check if step exists
        cursor.execute("""
            SELECT 1 FROM steps
            WHERE run_id = ? AND step_id = ? AND attempt = ?
        """, (step_data["run_id"], step_data["step_id"], step_data["attempt"]))
        
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update existing
            set_parts = []
            values = []
            for key, value in step_data.items():
                if key not in ("run_id", "step_id", "attempt"):
                    set_parts.append(f"{key} = ?")
                    values.append(value)
            
            values.extend([step_data["run_id"], step_data["step_id"], step_data["attempt"]])
            
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
        
        # Tool distribution
        cursor.execute(f"""
            SELECT tool, COUNT(*) as count
            FROM steps
            {where_clause}
            GROUP BY tool
            ORDER BY count DESC
            LIMIT 10
        """)
        tool_dist = {row["tool"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "events": event_count,
            "steps": step_count,
            "runs": run_count,
            "status_distribution": status_dist,
            "tool_distribution": tool_dist,
        }
    
    def commit(self):
        """Commit transaction"""
        if self.conn:
            self.conn.commit()
