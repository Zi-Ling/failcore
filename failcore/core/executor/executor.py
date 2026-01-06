# failcore/core/executor/executor.py
"""
Executor - execution orchestrator (refactored to use pipeline)

This executor is now a thin orchestrator that delegates to ExecutionPipeline.
All domain logic has been moved to dedicated modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import time

from failcore.core.types.step import Step, RunContext, StepResult, utc_now_iso
from ..tools import ToolProvider
from ..validate import ValidatorRegistry
from ..trace import TraceRecorder
from ..policy.policy import Policy
from ..replay.replayer import Replayer
from ..cost.execution import CostRunAccumulator, CostRecorder
from ..replay.execution import ReplayExecutionHook
from ..trace.summarize import SummarizeConfig, OutputSummarizer

from .state import ExecutionState, ExecutionServices
from .pipeline import ExecutionPipeline
from .output import OutputNormalizer
from .validation import StepValidator
from .failure import FailureBuilder
from .stages.dispatch import DispatchStage


# Cost tracking availability check
try:
    from ..cost import CostGuardian, CostEstimator, CostUsage, UsageExtractor
    from ...infra.storage.cost_tables import CostStorage
    COST_AVAILABLE = True
except ImportError:
    COST_AVAILABLE = False
    CostGuardian = None
    CostEstimator = None
    CostUsage = None
    UsageExtractor = None
    CostStorage = None


# Policy interface (backward compatibility)
class PolicyDeny(Exception):
    """Raised when policy denies an action"""
    pass


class Policy:
    """Minimal policy interface (backward compatibility)"""
    def allow(self, step: Step, ctx: RunContext) -> tuple[bool, str]:
        return True, ""


# Trace Recorder interface (backward compatibility)
class TraceRecorder:
    """Minimal recorder interface (backward compatibility)"""
    def record(self, event: Any) -> None:
        pass


@dataclass
class ExecutorConfig:
    """Executor configuration"""
    strict: bool = True
    include_stack: bool = True
    summarize_limit: int = 200
    enable_cost_tracking: bool = True


class Executor:
    """
    Executor - execution orchestrator
    
    This executor is now a thin wrapper around ExecutionPipeline.
    All domain logic has been moved to dedicated modules.
    """
    
    def __init__(
        self,
        tools: ToolProvider,
        recorder: Optional[TraceRecorder] = None,
        policy: Optional[Policy] = None,
        validator: Optional[ValidatorRegistry] = None,
        config: Optional[ExecutorConfig] = None,
        replayer: Optional[Replayer] = None,
        cost_guardian: Optional[CostGuardian] = None,
        cost_estimator: Optional[CostEstimator] = None,
        process_executor: Optional[Any] = None,  # Optional ProcessExecutor
        side_effect_boundary: Optional[Any] = None,  # Optional SideEffectBoundary for boundary enforcement
        guard_config: Optional[Any] = None,  # Optional GuardConfig for per-run guard configuration
    ) -> None:
        """
        Initialize executor
        
        Args:
            tools: Tool provider
            recorder: Trace recorder
            policy: Policy instance
            validator: Validator registry
            config: Executor configuration
            replayer: Optional replayer instance
            cost_guardian: Optional cost guardian
            cost_estimator: Optional cost estimator
            process_executor: Optional ProcessExecutor for isolated execution
            side_effect_boundary: Optional SideEffectBoundary instance.
                If provided, enables side-effect boundary gate (pre-execution checks).
                Default: None (gate disabled, no boundary enforcement).
                To enable: pass a SideEffectBoundary instance (e.g., from get_boundary("strict")).
            guard_config: Optional GuardConfig instance for per-run guard configuration.
                Controls semantic guard and taint tracking/DLP.
                Default: None (all guards disabled).
                To enable: pass GuardConfig(semantic=True, taint=True) from run() API.
        """
        self.tools = tools
        self.recorder = recorder or TraceRecorder()
        self.policy = policy or Policy()
        self.validator = validator
        self.config = config or ExecutorConfig()
        self.replayer = replayer
        self._attempt_counter = {}
        
        # Cost tracking setup
        cost_storage = None
        cost_guardian_instance = None
        cost_estimator_instance = None
        usage_extractor_instance = None
        
        if COST_AVAILABLE and self.config.enable_cost_tracking:
            from ...infra.storage.cost_tables import CostStorage
            from ..cost import CostGuardian, CostEstimator, UsageExtractor
            cost_storage = CostStorage()
            cost_guardian_instance = cost_guardian or CostGuardian()
            cost_estimator_instance = cost_estimator or CostEstimator()
            usage_extractor_instance = UsageExtractor()
        
        # Initialize domain services
        cost_accumulator = CostRunAccumulator()
        cost_recorder = CostRecorder(cost_storage) if cost_storage else None
        replay_hook = ReplayExecutionHook(replayer) if replayer else None
        output_normalizer = OutputNormalizer()
        step_validator = StepValidator(validator)
        summarize_config = SummarizeConfig(summarize_limit=self.config.summarize_limit)
        output_summarizer = OutputSummarizer(summarize_config)
        failure_builder = FailureBuilder(
            services=None,  # Will be set after services creation
            summarize_config=summarize_config,
        )
        
        # Initialize side-effect boundary gate (only if boundary explicitly provided)
        # Gate is disabled by default - user must explicitly pass a boundary to enable enforcement
        side_effect_gate = None
        if side_effect_boundary:
            from failcore.core.guards.effects.gate import SideEffectBoundaryGate
            side_effect_gate = SideEffectBoundaryGate(boundary=side_effect_boundary)
        
        # Guards (per-run configuration via guard_config)
        # Default: all guards disabled (zero cost, zero behavior)
        semantic_guard_instance = None
        dlp_middleware_instance = None
        taint_store_instance = None
        
        if guard_config:
            from ..config.guards import GuardConfig, is_semantic_enabled, is_taint_enabled
            
            # Semantic guard (if enabled in guard_config)
            if is_semantic_enabled(guard_config):
                try:
                    from ..guards.semantic import SemanticGuardMiddleware, RuleSeverity
                    semantic_guard_instance = SemanticGuardMiddleware(
                        enabled=True,
                        min_severity=RuleSeverity.HIGH,
                        block_on_violation=True,
                    )
                except ImportError:
                    # Semantic guard module not available - skip silently
                    pass
            
            # Taint tracking/DLP (if enabled in guard_config)
            if is_taint_enabled(guard_config):
                try:
                    from ..guards.taint import DLPMiddleware, TaintStore
                    # Create run-scoped taint store
                    taint_store_instance = TaintStore()
                    # Initialize DLP middleware with taint store
                    dlp_middleware_instance = DLPMiddleware(
                        taint_context=taint_store_instance.taint_context,
                        strict_mode=True,  # Default strict mode
                    )
                except ImportError:
                    # Taint module not available - skip silently
                    pass
        
        # Build ExecutionServices
        services = ExecutionServices(
            tools=tools,
            recorder=self.recorder,
            policy=self.policy,
            validator=validator,
            cost_guardian=cost_guardian_instance,
            cost_estimator=cost_estimator_instance,
            cost_storage=cost_storage,
            cost_accumulator=cost_accumulator,
            cost_recorder=cost_recorder,
            usage_extractor=usage_extractor_instance,
            replayer=replayer,
            replay_hook=replay_hook,
            output_normalizer=output_normalizer,
            step_validator=step_validator,
            side_effect_gate=side_effect_gate,
            semantic_guard=semantic_guard_instance,
            failure_builder=failure_builder,
        )
        
        # Set services in failure_builder (circular dependency workaround)
        failure_builder.services = services
        
        self.services = services
        
        # Initialize execution pipeline
        dispatch_stage = DispatchStage(process_executor=process_executor)
        self.pipeline = ExecutionPipeline([
            # Stages will be initialized by pipeline
        ])
        # Override default stages to include process_executor
        from .stages import (
            StartStage,
            ValidateStage,
            CostPrecheckStage,
            PolicyStage,
            ReplayStage,
            CostFinalizeStage,
        )
        self.pipeline.stages = [
            StartStage(),
            ValidateStage(),
            CostPrecheckStage(),
            PolicyStage(),
            ReplayStage(),
            dispatch_stage,
            CostFinalizeStage(),
        ]
    
    def execute(self, step: Step, ctx: RunContext) -> StepResult:
        """
        Execute a step
        
        Args:
            step: Step to execute
            ctx: Run context
        
        Returns:
            StepResult
        """
        # Track attempt number
        attempt = self._attempt_counter.get(step.id, 0) + 1
        self._attempt_counter[step.id] = attempt
        
        # Build execution state
        state = ExecutionState(
            step=step,
            ctx=ctx,
            run_ctx={},  # Will be set by StartStage
            attempt=attempt,
            started_at=utc_now_iso(),
            t0=time.perf_counter(),
        )
        
        # Execute pipeline
        result = self.pipeline.execute(state, self.services)
        
        return result
    
    def reset_run_cost(self, run_id: str) -> None:
        """Reset cumulative cost for a run (backward compatibility)"""
        self.services.cost_accumulator.reset(run_id)
    
    def get_run_cost(self, run_id: str) -> dict[str, Any]:
        """Get current cumulative cost for a run (backward compatibility)"""
        return self.services.cost_accumulator.get_cumulative(run_id)
