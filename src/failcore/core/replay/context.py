# failcore/core/replay/context.py
"""
Replay context for execution mode control
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any


class ReplayMode(str, Enum):
    """Replay execution modes"""
    REPORT = "report"  # audit mode - only report, no execution
    MOCK = "mock"  # Simulation mode - inject historical outputs
    RESUME = "resume"  # Resume from specific step


@dataclass
class ReplayContext:
    """
    Replay context passed to Executor
    
    This tells the executor:
    - Whether we're in replay mode
    - What replay mode
    - Where to get historical data
    """
    enabled: bool
    mode: ReplayMode
    trace_path: str
    replayer: Optional[Any] = None
    run_id_filter: Optional[str] = None
    resume_from_step: Optional[str] = None
    
    @classmethod
    def disabled(cls) -> "ReplayContext":
        """Create a disabled replay context"""
        return cls(
            enabled=False,
            mode=ReplayMode.MOCK,
            trace_path="",
        )
    
    @classmethod
    def mock(cls, trace_path: str, replayer=None) -> "ReplayContext":
        """Create a mock mode replay context"""
        return cls(
            enabled=True,
            mode=ReplayMode.MOCK,
            trace_path=trace_path,
            replayer=replayer,
        )
    
    @classmethod
    def report(cls, trace_path: str, replayer=None) -> "ReplayContext":
        """Create a report mode replay context"""
        return cls(
            enabled=True,
            mode=ReplayMode.REPORT,
            trace_path=trace_path,
            replayer=replayer,
        )
