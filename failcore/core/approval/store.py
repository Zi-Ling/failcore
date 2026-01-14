# failcore/core/approval/stor.py
"""
HITL Approval Plane - Store

Persistent storage for approval requests
"""

import json
from pathlib import Path
from typing import List, Optional
from .models import ApprovalRequest, ApprovalStatus


class ApprovalStore:
    """
    Store and manage approval requests
    
    Supports:
    - Save approval request
    - Load by request_id / run_id / step_id
    - List pending approvals
    - Update approval decision
    """
    
    def __init__(self, storage_path: str = "./.failcore/approvals"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def save(self, request: ApprovalRequest) -> None:
        """Save approval request to disk"""
        # Organize by run_id for easy cleanup
        run_dir = self.storage_path / request.run_id
        run_dir.mkdir(exist_ok=True)
        
        request_file = run_dir / f"{request.request_id}.json"
        with open(request_file, 'w') as f:
            json.dump(request.to_dict(), f, indent=2)
    
    def load(self, request_id: str, run_id: str = None) -> Optional[ApprovalRequest]:
        """Load approval request by ID"""
        if run_id:
            # Direct load if run_id known
            request_file = self.storage_path / run_id / f"{request_id}.json"
            if request_file.exists():
                return self._load_from_file(request_file)
        else:
            # Search across all runs
            for run_dir in self.storage_path.iterdir():
                if run_dir.is_dir():
                    request_file = run_dir / f"{request_id}.json"
                    if request_file.exists():
                        return self._load_from_file(request_file)
        
        return None
    
    def _load_from_file(self, filepath: Path) -> ApprovalRequest:
        """Load approval request from file"""
        with open(filepath) as f:
            data = json.load(f)
        
        from .models import RiskLevel
        
        return ApprovalRequest(
            request_id=data["request_id"],
            run_id=data["run_id"],
            step_id=data["step_id"],
            trace_id=data.get("trace_id"),
            tool_name=data["tool_name"],
            params_summary=data.get("params_summary", {}),
            risk_level=RiskLevel(data.get("risk_level", "high")),
            risk_reason=data.get("risk_reason", ""),
            status=ApprovalStatus(data["status"]),
            requested_at=data["requested_at"],
            decided_at=data.get("decided_at"),
            decided_by=data.get("decided_by"),
            decision_reason=data.get("decision_reason"),
            timeout_seconds=data.get("timeout_seconds", 300),
            context=data.get("context", {}),
        )
    
    def list_pending(self, run_id: str = None) -> List[ApprovalRequest]:
        """List all pending approval requests"""
        pending = []
        
        if run_id:
            # List for specific run
            run_dir = self.storage_path / run_id
            if run_dir.exists():
                for request_file in run_dir.glob("*.json"):
                    request = self._load_from_file(request_file)
                    if request.is_pending():
                        pending.append(request)
        else:
            # List across all runs
            for run_dir in self.storage_path.iterdir():
                if run_dir.is_dir():
                    for request_file in run_dir.glob("*.json"):
                        request = self._load_from_file(request_file)
                        if request.is_pending():
                            pending.append(request)
        
        # Sort by requested_at (oldest first)
        pending.sort(key=lambda r: r.requested_at)
        return pending
    
    def update(self, request: ApprovalRequest) -> None:
        """Update approval request (after decision)"""
        self.save(request)  # Overwrite with updated state
    
    def delete(self, request_id: str, run_id: str) -> bool:
        """Delete approval request"""
        request_file = self.storage_path / run_id / f"{request_id}.json"
        if request_file.exists():
            request_file.unlink()
            return True
        return False


__all__ = ["ApprovalStore"]
