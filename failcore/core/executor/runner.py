from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, Union

from .executor import Executor
from failcore.core.types.step import Step, RunContext, StepResult, StepStatus


# ---------------------------
# Planner output types
# ---------------------------

@dataclass
class Final:
    message: str


class Planner(Protocol):
    def decide(self, state: "AgentState") -> Union[Step, Final]:
        ...


# ---------------------------
# State
# ---------------------------

@dataclass
class AgentState:
    goal: str
    done: bool = False
    final: Optional[str] = None

    # last execution result for planner / debugging
    last_result: Optional[StepResult] = None

    # lightweight history for planner / observability (not the trace.jsonl)
    history: list[Dict[str, Any]] = field(default_factory=list)

    # step id counter (runner-owned)
    step_idx: int = 0


# ---------------------------
# Runner
# ---------------------------

@dataclass
class RunnerConfig:
    max_steps: int = 20
    stop_on_fail: bool = True


class Runner:
    """
    Agent loop orchestrator:
      - calls planner for next Step (or Final)
      - uses Executor to execute exactly one Step
      - updates AgentState (history + last_result)
      - stops on Final / max_steps / (optional) failure
    """

    def __init__(
        self,
        executor: Executor,
        planner: Planner,
        config: Optional[RunnerConfig] = None,
    ) -> None:
        self.executor = executor
        self.planner = planner
        self.config = config or RunnerConfig()

    def _ensure_step_id(self, step: Step, state: AgentState) -> None:
        sid = getattr(step, "id", None)
        if not sid or not str(sid).strip():
            state.step_idx += 1
            step.id = f"s{state.step_idx}"

    def run(self, state: AgentState, ctx: RunContext) -> AgentState:
        for _ in range(self.config.max_steps):
            if state.done:
                break

            decision = self.planner.decide(state)

            # Done
            if isinstance(decision, Final):
                state.done = True
                state.final = decision.message
                return state

            # Next step
            step = decision
            self._ensure_step_id(step, state)

            result = self.executor.execute(step, ctx)
            state.last_result = result

            state.history.append(
                {
                    "step_id": result.step_id,
                    "tool": result.tool,
                    "status": result.status.value,
                    "started_at": result.started_at,
                    "finished_at": result.finished_at,
                    "duration_ms": result.duration_ms,
                    "output_kind": (result.output.kind.value if result.output else None),
                    "output": (result.output.value if result.output else None),
                    "error_code": (result.error.error_code if result.error else None),
                    "error_message": (result.error.message if result.error else None),
                }
            )

            # Optional: stop on failure
            if self.config.stop_on_fail and result.status == StepStatus.FAIL:
                state.done = True
                state.final = f"failed: {result.error.error_code if result.error else 'unknown'}"
                return state

        # Max steps reached
        state.done = True
        state.final = "max_steps reached"
        return state
