"""
P2-2: Execution Receipt (Immutable Proof of Execution)

A Receipt is an immutable record of a tool call:
- Input parameters hash
- Policy decision
- Environment snapshot (sandbox/policy version)
- Output summary (hash + size)
- Error structure (FailCoreError)
- Replay pointer (optional)

Supports two replay modes:
1. Deterministic replay: Use recorded result (testing/debugging)
2. Resume from step N: Continue from checkpoint (orchestration)
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
from datetime import datetime, timezone


@dataclass
class Receipt:
    """
    Immutable execution receipt
    
    Proof of what happened during tool execution
    """
    # Identity
    receipt_id: str
    run_id: str
    step_id: str
    tool_name: str
    
    # Input
    params_hash: str  # SHA256 of sorted JSON
    params_summary: Dict[str, Any]  # Truncated for display
    
    # Context
    sandbox: Optional[str]
    policy_version: str
    policy_decision: str  # ALLOWED, DENIED, BYPASSED
    
    # Execution
    started_at: str
    finished_at: str
    duration_ms: int
    status: str  # SUCCESS, FAIL, BLOCKED
    
    # Output
    output_hash: Optional[str] = None  # SHA256 if success
    output_size: Optional[int] = None
    output_summary: Optional[Dict[str, Any]] = None
    
    # Error
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_suggestion: Optional[str] = None
    error_remediation: Optional[Dict[str, Any]] = None
    
    # Replay
    replay_enabled: bool = False
    replay_result: Optional[Any] = None  # For deterministic replay
    
    # Metadata
    attempt: int = 1
    retry_of: Optional[str] = None  # receipt_id of previous attempt
    
    @classmethod
    def from_step_result(cls, step_result: Any, run_id: str, step_params: Dict[str, Any], context: Dict[str, Any]) -> "Receipt":
        """
        Create receipt from StepResult
        
        Args:
            step_result: StepResult object
            run_id: Run ID
            step_params: Original step parameters (from Step.params)
            context: Execution context
        """
        params_hash = cls._hash_params(step_params)
        
        # Extract error if present
        error = step_result.error if hasattr(step_result, 'error') else None
        error_code = None
        error_message = None
        error_suggestion = None
        error_remediation = None
        
        if error:
            error_code = error.error_code if hasattr(error, 'error_code') else None
            error_message = error.message if hasattr(error, 'message') else str(error)
            if hasattr(error, 'detail') and isinstance(error.detail, dict):
                error_suggestion = error.detail.get('suggestion')
                error_remediation = error.detail.get('remediation')
        
        # Extract output (StepResult.output is a StepOutput object)
        output = step_result.output if hasattr(step_result, 'output') else None
        output_hash = None
        output_size = None
        output_summary = None
        
        if output:
            # StepOutput has .value attribute
            output_value = output.value if hasattr(output, 'value') else output
            if output_value is not None:
                output_str = json.dumps(output_value, sort_keys=True, default=str)
                output_hash = hashlib.sha256(output_str.encode()).hexdigest()
                output_size = len(output_str)
                output_summary = cls._summarize_output(output_value)
        
        return cls(
            receipt_id=f"rcpt_{step_result.step_id}_{datetime.now(timezone.utc).timestamp()}",
            run_id=run_id,
            step_id=step_result.step_id,
            tool_name=step_result.tool if hasattr(step_result, 'tool') else "unknown",
            params_hash=params_hash,
            params_summary=cls._summarize_params(step_params),
            sandbox=context.get('sandbox'),
            policy_version=context.get('policy_version', '1.0'),
            policy_decision=context.get('policy_decision', 'ALLOWED'),
            started_at=step_result.started_at if hasattr(step_result, 'started_at') else "",
            finished_at=step_result.finished_at if hasattr(step_result, 'finished_at') else "",
            duration_ms=step_result.duration_ms if hasattr(step_result, 'duration_ms') else 0,
            status=str(step_result.status) if hasattr(step_result, 'status') else "UNKNOWN",
            output_hash=output_hash,
            output_size=output_size,
            output_summary=output_summary,
            error_code=error_code,
            error_message=error_message,
            error_suggestion=error_suggestion,
            error_remediation=error_remediation,
        )
    
    @staticmethod
    def _hash_params(params: Dict[str, Any]) -> str:
        """Hash parameters for deduplication"""
        params_str = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(params_str.encode()).hexdigest()
    
    @staticmethod
    def _summarize_params(params: Dict[str, Any], max_len: int = 100) -> Dict[str, Any]:
        """Truncate params for display"""
        summary = {}
        for key, value in params.items():
            value_str = str(value)
            if len(value_str) > max_len:
                summary[key] = value_str[:max_len] + "..."
            else:
                summary[key] = value
        return summary
    
    @staticmethod
    def _summarize_output(output: Any, max_len: int = 200) -> Dict[str, Any]:
        """Summarize output for display"""
        output_str = str(output)
        if len(output_str) > max_len:
            return {"preview": output_str[:max_len] + "...", "truncated": True}
        return {"preview": output_str, "truncated": False}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage"""
        return asdict(self)
    
    def enable_replay(self, result: Any):
        """Enable deterministic replay with this result"""
        self.replay_enabled = True
        self.replay_result = result


class ReceiptStore:
    """
    Store and query execution receipts
    
    Supports:
    - Save receipt after each step
    - Query by run_id, step_id, tool_name
    - Replay from receipt
    - Resume from step N
    """
    
    def __init__(self, storage_path: str = "./.failcore/receipts"):
        from pathlib import Path
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def save(self, receipt: Receipt):
        """Save receipt to storage"""
        run_dir = self.storage_path / receipt.run_id
        run_dir.mkdir(exist_ok=True)
        
        receipt_file = run_dir / f"{receipt.step_id}.json"
        with open(receipt_file, 'w') as f:
            json.dump(receipt.to_dict(), f, indent=2)
    
    def load(self, run_id: str, step_id: str) -> Optional[Receipt]:
        """Load receipt from storage"""
        receipt_file = self.storage_path / run_id / f"{step_id}.json"
        
        if not receipt_file.exists():
            return None
        
        with open(receipt_file) as f:
            data = json.load(f)
            return Receipt(**data)
    
    def list_for_run(self, run_id: str) -> list[Receipt]:
        """List all receipts for a run"""
        run_dir = self.storage_path / run_id
        
        if not run_dir.exists():
            return []
        
        receipts = []
        for receipt_file in sorted(run_dir.glob("*.json")):
            with open(receipt_file) as f:
                data = json.load(f)
                receipts.append(Receipt(**data))
        
        return receipts
    
    def can_replay(self, receipt: Receipt) -> bool:
        """Check if receipt can be used for deterministic replay"""
        return receipt.replay_enabled and receipt.replay_result is not None
    
    def find_last_success(self, run_id: str) -> Optional[Receipt]:
        """Find last successful step for resume"""
        receipts = self.list_for_run(run_id)
        
        for receipt in reversed(receipts):
            if receipt.status == "SUCCESS":
                return receipt
        
        return None


__all__ = ["Receipt", "ReceiptStore"]
