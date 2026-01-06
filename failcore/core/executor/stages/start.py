# failcore/core/executor/stages/start.py
"""
Start Stage - record STEP_START event and initialize execution state
"""

from typing import Optional, Any

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult
from ...trace import build_step_start_event, build_run_context


class StartStage:
    """Stage 1: Record STEP_START and initialize state"""
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Record STEP_START event and initialize state.seq
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            None (always continues to next stage)
        """
        # Build run context for tracing
        run_ctx = build_run_context(
            run_id=state.ctx.run_id,
            created_at=state.ctx.created_at,
            workspace=None,
            sandbox_root=state.ctx.sandbox_root,
            cwd=state.ctx.cwd,
            tags=state.ctx.tags,
            flags=state.ctx.flags,
        )
        state.run_ctx = run_ctx
        
        # Record STEP_START
        if hasattr(services.recorder, 'next_seq'):
            seq = services.recorder.next_seq()
            state.seq = seq
            
            self._record(
                services,
                build_step_start_event(
                    seq=seq,
                    run_context=run_ctx,
                    step_id=state.step.id,
                    tool=state.step.tool,
                    params=state.step.params,
                    attempt=state.attempt,
                    depends_on=state.step.depends_on,
                )
            )
        
        return None  # Continue to next stage
    
    def _record(self, services: ExecutionServices, event: Any) -> None:
        """Record trace event (fail-safe)"""
        try:
            services.recorder.record(event)
        except Exception:
            pass
