# failcore/web/services/repos/cost_repo_sqlite.py
"""
Cost Repository - SQLite implementation

Provides data access abstraction for SQLite cost storage.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

from failcore.infra.storage.cost_tables import CostStorage
from failcore.utils.paths import get_database_path


class CostRepoSqlite:
    """
    SQLite repository for cost data
    
    Provides abstraction layer over CostStorage, isolating
    service layer from storage implementation details.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize SQLite repository
        
        Args:
            db_path: Optional database path (defaults to get_database_path())
        """
        if db_path is None:
            db_path = get_database_path()
        self.cost_storage = CostStorage(db_path=db_path)
    
    def get_run_curve(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get cost curve for a run
        
        Args:
            run_id: Run ID
        
        Returns:
            List of usage records (ordered by seq)
        """
        try:
            return self.cost_storage.get_run_curve(run_id)
        except Exception:
            return []
    
    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run summary (total cost, tokens, etc.)
        
        Args:
            run_id: Run ID
        
        Returns:
            Run summary dict or None if not found
        """
        try:
            return self.cost_storage.get_run_summary(run_id)
        except Exception:
            return None
    
    def get_budget_for_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get budget snapshot for a run
        
        Args:
            run_id: Run ID
        
        Returns:
            Budget snapshot dict or None if not found
        """
        try:
            return self.cost_storage.get_budget_for_run(run_id)
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """
        Check if SQLite storage is available
        
        Returns:
            True if available, False otherwise
        """
        try:
            # Try to access database
            db_path = get_database_path()
            return db_path.exists() or db_path.parent.exists()
        except Exception:
            return False


__all__ = ["CostRepoSqlite"]
