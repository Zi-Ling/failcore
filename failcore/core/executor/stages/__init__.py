# failcore/core/executor/stages/__init__.py
"""
Execution Stages - modular execution pipeline stages

Each stage implements a single responsibility in the execution pipeline.
Stages receive ExecutionState and ExecutionServices, return Optional[StepResult].
"""

from .start import StartStage
from .validate import ValidateStage
from .cost_precheck import CostPrecheckStage
from .policy import PolicyStage
from .replay import ReplayStage
from .dispatch import DispatchStage
from .cost_finalize import CostFinalizeStage

__all__ = [
    "StartStage",
    "ValidateStage",
    "CostPrecheckStage",
    "PolicyStage",
    "ReplayStage",
    "DispatchStage",
    "CostFinalizeStage",
]
