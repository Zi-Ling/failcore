# failcore/core/executor/pipeline.py
"""
Execution Pipeline - orchestrates execution stages
"""

from typing import List, Optional

from .state import ExecutionState, ExecutionServices
from .stages import (
    StartStage,
    ValidateStage,
    CostPrecheckStage,
    PolicyStage,
    ReplayStage,
    DispatchStage,
    CostFinalizeStage,
)
from failcore.core.types.step import StepResult


class ExecutionStage:
    """Base interface for execution stages"""
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Execute stage logic
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult if execution should stop, None to continue
        """
        raise NotImplementedError


class ExecutionPipeline:
    """
    Execution pipeline orchestrator
    
    Executes stages in sequence, stopping early if a stage returns StepResult.
    """
    
    def __init__(self, stages: Optional[List[ExecutionStage]] = None):
        """
        Initialize pipeline
        
        Args:
            stages: Optional list of stages (uses default if None)
        """
        if stages is None:
            # Default pipeline stages
            self.stages = [
                StartStage(),
                ValidateStage(),
                CostPrecheckStage(),
                PolicyStage(),
                ReplayStage(),
                DispatchStage(),
                CostFinalizeStage(),
            ]
        else:
            self.stages = stages
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> StepResult:
        """
        Execute pipeline
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult (success or failure)
        
        Note:
            - Stages execute in order
            - If a stage returns StepResult, pipeline stops and returns it
            - If all stages return None, builds success StepResult
        """
        # Execute stages in order
        for stage in self.stages:
            result = stage.execute(state, services)
            if result is not None:
                # Stage returned result - stop pipeline
                return result
        
        # All stages passed - build success result
        return self._build_success_result(state, services)
    
    def _build_success_result(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> StepResult:
        """Build success StepResult"""
        from failcore.core.types.step import StepStatus, utc_now_iso
        import time
        
        finished_at = utc_now_iso()
        duration_ms = int((time.perf_counter() - state.t0) * 1000)
        
        # Record RESULT event (success)
        if hasattr(services.recorder, 'next_seq') and state.seq is not None:
            seq = services.recorder.next_seq()
            from ..trace import build_result_event, ExecutionPhase
            # Use StepStatus from step module (not trace.events)
            
            # Summarize output if summarizer available
            output_summary = None
            if state.output and hasattr(services.failure_builder, 'summarizer') and services.failure_builder.summarizer:
                output_summary = services.failure_builder.summarizer.summarize_output(state.output)
            elif state.output:
                output_summary = {
                    "kind": state.output.kind.value if hasattr(state.output.kind, 'value') else str(state.output.kind),
                    "value": state.output.value,
                }
            
            from ..trace.status_mapping import map_step_status_to_trace

            # Map execution status to trace status
            trace_status = map_step_status_to_trace(StepStatus.OK)
            
            services.recorder.record(
                build_result_event(
                    seq=seq,
                    run_context=state.run_ctx,
                    step_id=state.step.id,
                    tool=state.step.tool,
                    attempt=state.attempt,
                    status=trace_status,
                    phase=ExecutionPhase.EXECUTE,
                    duration_ms=duration_ms,
                    output=output_summary,
                    metrics=state.cost_metrics,
                )
            )
            
            # Record to cost storage (handled by CostFinalizeStage)
            # Pipeline doesn't need to duplicate this logic
        
        return StepResult(
            step_id=state.step.id,
            tool=state.step.tool,
            status=StepStatus.OK,
            started_at=state.started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            output=state.output,
            error=None,
            meta={},
        )


__all__ = [
    "ExecutionStage",
    "ExecutionPipeline",
]
