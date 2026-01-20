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
    from ...infra.storage.cost import CostStorage
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
    """
    Executor configuration
    
    Controls executor behavior including cost tracking, output handling, and timeout enforcement.
    """
    strict: bool = True
    include_stack: bool = True
    summarize_limit: int = 200
    enable_cost_tracking: bool = True
    
    # Timeout configuration (阶段四：超时系统化)
    default_timeout: Optional[float] = 300.0  # Default: 5 minutes per step
    max_timeout: Optional[float] = 3600.0  # Maximum allowed timeout: 1 hour
    enable_timeout_enforcement: bool = True  # If False, timeouts are advisory only
    timeout_kill_process_group: bool = True  # If True, kill process group on timeout (not entire session)
    
    def get_effective_timeout(
        self, 
        step_params: Optional[dict] = None,
        tool_spec: Optional[Any] = None
    ) -> tuple[Optional[float], dict]:
        """
        Get effective timeout for a step with priority rules
        
        步骤2：优先级规则（从高到低）：
        1. step.__timeout (显式指定)
        2. tool-level default (tool_spec.timeout，未来支持)
        3. config.default_timeout
        最终 clamp 到 max_timeout
        
        Args:
            step_params: Step parameters (may contain __timeout)
            tool_spec: Tool specification (may contain default timeout, 未来支持)
            
        Returns:
            Tuple of (effective_timeout, metadata)
            - effective_timeout: Timeout in seconds, or None if disabled
            - metadata: Dict with {source, original, clamped, clamp_reason}
        """
        metadata = {
            "source": None,
            "original": None,
            "clamped": False,
            "clamp_reason": None,
        }
        
        if not self.enable_timeout_enforcement:
            metadata["source"] = "disabled"
            return (None, metadata)
        
        # Priority 1: Step-specific __timeout
        timeout = None
        if step_params and isinstance(step_params, dict) and "__timeout" in step_params:
            timeout = step_params["__timeout"]
            metadata["source"] = "step_explicit"
            metadata["original"] = timeout
        
        # Priority 2: Tool-level default (未来支持)
        elif tool_spec and hasattr(tool_spec, 'timeout') and tool_spec.timeout is not None:
            timeout = tool_spec.timeout
            metadata["source"] = "tool_default"
            metadata["original"] = timeout
        
        # Priority 3: Config default
        elif self.default_timeout is not None:
            timeout = self.default_timeout
            metadata["source"] = "config_default"
            metadata["original"] = timeout
        
        if timeout is None:
            metadata["source"] = "none"
            return (None, metadata)
        
        # Enforce max_timeout limit (clamp)
        if self.max_timeout is not None and timeout > self.max_timeout:
            metadata["clamped"] = True
            metadata["clamp_reason"] = f"Exceeded max_timeout ({self.max_timeout}s), clamped from {timeout}s"
            timeout = self.max_timeout
        
        return (timeout, metadata)


class Executor:
    """
    Executor - execution orchestrator
    
    This executor is now a thin wrapper around ExecutionPipeline.
    All domain logic has been moved to dedicated modules.
    """
    
    def __init__(
        self,
        tools: ToolProvider,
        session_resources: Optional[Any] = None,  # SessionResources (PREFERRED, enforces resource ownership)
        recorder: Optional[TraceRecorder] = None,  # DEPRECATED: use session_resources
        policy: Optional[Policy] = None,
        validation_engine: Optional[Any] = None,  # Optional ValidationEngine
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
        
        IMPORTANT: Prefer using session_resources parameter for proper resource management.
        Direct resource parameters (recorder, etc.) are deprecated and will be removed.
        
        Args:
            tools: Tool provider
            session_resources: SessionResources instance (PREFERRED).
                Contains all session-owned resources (registry, recorder, janitor, sandbox).
                If provided, overrides individual resource parameters.
            recorder: Trace recorder (DEPRECATED: use session_resources)
            policy: Policy instance
            validation_engine: Optional ValidationEngine for validation
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
        
        # Resource management: prefer session_resources over individual parameters
        if session_resources:
            # Validate session_resources has proper creation token
            from failcore.core.executor.resources import SessionResources
            if not isinstance(session_resources, SessionResources):
                raise TypeError(
                    f"session_resources must be SessionResources instance, got {type(session_resources)}"
                )
            
            if not session_resources.validate_token():
                raise RuntimeError(
                    "Invalid SessionResources: must be created through Session.create_resources()"
                )
            
            # Use resources from session_resources
            self.recorder = session_resources.trace_recorder
            process_registry_instance = session_resources.process_registry
            self.session_resources = session_resources
            
            import logging
            logging.info(f"Executor initialized with SessionResources (session_id={session_resources.session_id})")
        else:
            # Legacy path: create resources independently (DEPRECATED)
            import warnings
            warnings.warn(
                "Creating Executor without SessionResources is deprecated. "
                "Use Session.create_executor() or pass session_resources parameter.",
                DeprecationWarning,
                stacklevel=2
            )
            
            self.recorder = recorder or TraceRecorder()
            
            # Create process registry (legacy, not managed by Session)
            from ..process import ProcessRegistry
            process_registry_instance = ProcessRegistry()
            self.session_resources = None
        
        self.policy = policy or Policy()
        self.validation_engine = validation_engine
        self.config = config or ExecutorConfig()
        self.replayer = replayer
        self._attempt_counter = {}
        
        # Cost tracking setup
        cost_storage = None
        cost_guardian_instance = None
        cost_estimator_instance = None
        usage_extractor_instance = None
        
        if COST_AVAILABLE and self.config.enable_cost_tracking:
            from ...infra.storage.cost import CostStorage
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
        step_validator = StepValidator(validation_engine=self.validation_engine)
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
            side_effect_gate = SideEffectBoundaryGate(
                boundary=side_effect_boundary,
                tool_provider=tools,  # Pass tool provider for metadata-based prediction
            )
        
        # Guards (per-run configuration via guard_config)
        # Default: all guards disabled (zero cost, zero behavior)
        semantic_guard_instance = None
        dlp_middleware_instance = None
        taint_store_instance = None
        
        if guard_config:
            from ...config.guards import is_semantic_enabled, is_taint_enabled
            
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
            validation_engine=self.validation_engine,
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
            taint_engine=dlp_middleware_instance,
            taint_store=taint_store_instance,
            process_registry=process_registry_instance,
            executor_config=self.config,  # 阶段四：传递config用于超时
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
