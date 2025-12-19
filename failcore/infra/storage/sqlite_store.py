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
        
        # Store schema version
        cursor.execute("""
            INSERT OR REPLACE INTO _metadata (key, value)
            VALUES ('schema_version', ?)
        """, (self.SCHEMA_VERSION,))
        
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        # Count events
        cursor.execute("SELECT COUNT(*) as count FROM events")
        event_count = cursor.fetchone()["count"]
        
        # Count steps
        cursor.execute("SELECT COUNT(*) as count FROM steps")
        step_count = cursor.fetchone()["count"]
        
        # Count runs
        cursor.execute("SELECT COUNT(DISTINCT run_id) as count FROM events")
        run_count = cursor.fetchone()["count"]
        
        # Status distribution
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM steps
            WHERE status IS NOT NULL
            GROUP BY status
            ORDER BY count DESC
        """)
        status_dist = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # Tool distribution
        cursor.execute("""
            SELECT tool, COUNT(*) as count
            FROM steps
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
            "top_tools": tool_dist,
        }
    
    def commit(self):
        """Commit transaction"""
        if self.conn:
            self.conn.commit()
