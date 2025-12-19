from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..executor.executor import StepResult  # 或者从 ..step import StepResult（看你实际放哪）

@dataclass
class AgentState:
    goal: str
    done: bool = False
    final: Optional[str] = None

    # 给 planner 用的“短记忆”
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_result: Optional[StepResult] = None

    # 生成 step id 用
    step_idx: int = 0
