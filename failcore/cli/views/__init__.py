# failcore/cli/views/base.py
"""
View models for FailCore CLI

Views are stable, serializable output structures that separate:
- What happened (View)
- How to display it (Renderer)
"""

from .trace_show import TraceShowView
from .replay_run import ReplayRunView
from .replay_diff import ReplayDiffView
from .trace_report import TraceReportView

__all__ = [
    "TraceShowView",
    "ReplayRunView",
    "ReplayDiffView",
    "TraceReportView",
]
