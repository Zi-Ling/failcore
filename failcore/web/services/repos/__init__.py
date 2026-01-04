# failcore/web/services/repos/__init__.py
"""
Repository layer for data access

Separates data access logic from service layer, making it easy to swap
storage implementations (SQLite, trace files, remote DB, etc.)
"""

from .cost_repo_sqlite import CostRepoSqlite
from .cost_repo_trace import CostRepoTrace

__all__ = ["CostRepoSqlite", "CostRepoTrace"]
