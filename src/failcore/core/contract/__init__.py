# failcore/core/contract/base.py
"""
Contract layer - Semantic validation and drift detection

This layer provides:
- Contract validation rules (kind, schema, etc.)
- Structured results for trace integration
- Clear decision semantics (OK, WARN, BLOCK)

It does NOT handle:
- Trace recording (that's trace/)
- Policy enforcement (that's policy/)
- Execution flow (that's executor/)
"""

from .types import ExpectedKind, DriftType, Decision
from .model import ContractResult
from .checkers import ContractChecker, check_output

__all__ = [
    # Types
    "ExpectedKind",
    "DriftType",
    "Decision",
    
    # Model
    "ContractResult",
    
    # Checkers
    "ContractChecker",
    "check_output",
]

