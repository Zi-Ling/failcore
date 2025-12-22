# failcore/api/result.py
"""
Result types - user-friendly aliases for step execution results
"""

from ..core.step import (
    StepResult,
    StepStatus,
    StepError,
    StepOutput,
    OutputKind,
    ArtifactRef,
)

# Export StepResult as Result for more product-like naming
Result = StepResult

__all__ = [
    "Result",
    "StepResult",
    "StepStatus",
    "StepError",
    "StepOutput",
    "OutputKind",
    "ArtifactRef",
]
