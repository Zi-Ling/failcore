# failcore/infra/storage/base.py
"""
Storage engines for trace persistence and querying
"""

from .sqlite_store import SQLiteStore
from .ingest import TraceIngestor

__all__ = [
    "SQLiteStore",
    "TraceIngestor",
]
