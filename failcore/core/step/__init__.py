# failcore/core/step/__init__.py
"""
Core step types for Failcore.

This package defines the basic building blocks for expressing
executable steps in a Failcore workflow.

No side effects on import.
"""

from .step import Step, RunContext, StepResult, StepStatus, StepError, StepOutput, OutputKind, ArtifactRef, utc_now_iso

__all__ = [
    "Step",
    "RunContext",
    "StepResult",
    "StepStatus",
    "StepError",
    "StepOutput",
    "OutputKind",
    "ArtifactRef",
    "utc_now_iso",
]
