# failcore/core/executor/state.py
"""
Execution State and Services - context and dependency injection

This module defines:
- ExecutionState: Execution context state passed between stages
- ExecutionServices: Explicit service interface (adopts suggestion 5)

Design principle:
- Stage receives only allowed services, not full executor
- Prevents stages from accessing executor private state
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, TYPE_CHECKING

from failcore.core.types.step import Step, RunContext, StepOutput, StepError
from ..tools import ToolProvider
from ..validate import ValidatorRegistry
from ..trace import TraceRecorder
from ..policy.policy import Policy
from ..cost import CostGuardian, CostEstimator, CostUsage, UsageExtractor
from ..cost.execution import CostRunAccumulator, CostRecorder
from ..replay.execution import ReplayExecutionHook
from ..replay.replayer import Replayer
from .output import OutputNormalizer
from .validation import StepValidator
from ...infra.storage.cost_tables import CostStorage

# Avoid circular import
if TYPE_CHECKING:
    from .failure import FailureBuilder


@dataclass
class ExecutionState:
    """
    Execution context state passed between stages
    
    Contains all state that needs to be shared across execution stages.
    """
    step: Step
    ctx: RunContext
    run_ctx: Dict[str, Any]  # Trace run context dict
    attempt: int
    started_at: str
    t0: float  # Performance counter start time
    
    # Optional state (populated by stages)
    seq: Optional[int] = None
    estimated_usage: Optional[CostUsage] = None
    actual_usage: Optional[CostUsage] = None
    cost_metrics: Optional[Dict[str, Any]] = None
    policy_result: Optional[Any] = None  # PolicyResult or tuple
    replay_decision: Optional[Any] = None  # ReplayDecision
    output: Optional[StepOutput] = None
    error: Optional[StepError] = None
    
    # Side-effect tracking (two-phase: prediction + observation)
    predicted_side_effects: List[Any] = field(default_factory=list)  # PredictedSideEffect list
    observed_side_effects: List[Any] = field(default_factory=list)  # SideEffectEvent list
    
    # Taint tracking state
    original_params: Optional[Dict[str, Any]] = None  # Original params before sanitization
    sanitized_params: Optional[Dict[str, Any]] = None  # Sanitized params (if DLP sanitized)
    taint_tags: List[Any] = field(default_factory=list)  # Current step's taint tags


@dataclass
class ExecutionServices:
    """
    Explicit service interface (adopts suggestion 5)
    
    Stages receive only these services, not the full executor.
    This prevents stages from accessing executor private state.
    """
    # Core services
    tools: ToolProvider
    recorder: TraceRecorder
    policy: Policy
    validator: Optional[ValidatorRegistry]
    
    # Cost services
    cost_guardian: Optional[CostGuardian]
    cost_estimator: Optional[CostEstimator]
    cost_storage: Optional[CostStorage]
    cost_accumulator: CostRunAccumulator
    cost_recorder: Optional[CostRecorder]
    usage_extractor: Optional[UsageExtractor]
    
    # Replay services
    replayer: Optional[Replayer]
    replay_hook: Optional[ReplayExecutionHook]
    
    # Output/validation services
    output_normalizer: OutputNormalizer
    step_validator: StepValidator
    
    # Failure handling
    failure_builder: "FailureBuilder"
    
    # Side-effect boundary gate (optional, must be after required fields)
    side_effect_gate: Optional[Any] = None  # SideEffectBoundaryGate
    
    # Semantic guard (optional, must be after required fields)
    semantic_guard: Optional[Any] = None  # SemanticGuardMiddleware
    
    # Taint tracking/DLP (optional, must be after required fields)
    taint_engine: Optional[Any] = None  # DLPMiddleware
    taint_store: Optional[Any] = None  # TaintStore (run-scoped)


__all__ = [
    "ExecutionState",
    "ExecutionServices",
]
