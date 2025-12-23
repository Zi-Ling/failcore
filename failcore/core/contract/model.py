# failcore/core/contract/model.py
"""
Contract validation result model
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from .types import Decision, DriftType, ExpectedKind


@dataclass
class ContractResult:
    """
    Structured result of contract validation
    
    This model bridges contract checking and trace events.
    Maps to OUTPUT_NORMALIZED trace event when drift is detected.
    """
    decision: Decision
    drift_type: Optional[DriftType] = None
    expected_kind: Optional[ExpectedKind] = None
    observed_kind: Optional[str] = None
    reason: Optional[str] = None
    raw_excerpt: Optional[str] = None
    
    # Optional detailed diagnostics
    parse_error: Optional[str] = None
    fields_missing: List[str] = field(default_factory=list)
    schema_errors: List[str] = field(default_factory=list)
    
    def to_trace_event(self) -> Dict[str, Any]:
        """
        Convert to CONTRACT_DRIFT trace event data
        
        Returns event.data structure compatible with trace schema v0.1.1:
        event.data = {
            "contract": {
                "drift_type": "output_kind_mismatch",
                "expected_kind": "json",
                "observed_kind": "text",
                "decision": "warn",  # or "block"
                "reason": "...",
                "excerpt": "..."  # optional
            }
        }
        
        Returns:
            Dictionary compatible with trace event.data structure
        """
        if self.decision == Decision.OK:
            return {}
        
        contract_data = {
            "drift_type": self.drift_type.value if self.drift_type else None,
            "expected_kind": self.expected_kind.value if self.expected_kind else None,
            "observed_kind": self.observed_kind,
            "decision": self.decision.value,
            "reason": self.reason,
        }
        
        # Add optional diagnostics
        if self.raw_excerpt:
            contract_data["excerpt"] = self.raw_excerpt
        if self.parse_error:
            contract_data["parse_error"] = self.parse_error
        if self.fields_missing:
            contract_data["fields_missing"] = self.fields_missing
        
        return {"contract": contract_data}
    
    def is_ok(self) -> bool:
        """Check if contract is satisfied"""
        return self.decision == Decision.OK
    
    def should_warn(self) -> bool:
        """Check if warning should be issued"""
        return self.decision == Decision.WARN
    
    def should_block(self) -> bool:
        """Check if execution should be blocked"""
        return self.decision == Decision.BLOCK

