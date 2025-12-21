# failcore/cli/renderers/json.py
"""
JSON renderer for Views - Machine-readable output for CI/tools
"""

import json
from typing import Any
from ..views.replay_run import ReplayRunView
from ..views.replay_diff import ReplayDiffView
from ..views.trace_show import TraceShowView


class JsonRenderer:
    """
    JSON renderer for all view types
    
    Outputs stable, machine-readable JSON for:
    - CI pipelines
    - Log aggregation
    - Programmatic consumption
    """
    
    def __init__(self, indent: int = 2):
        self.indent = indent
    
    def render_replay_run(self, view: ReplayRunView) -> str:
        """Render ReplayRunView as JSON"""
        return json.dumps(view.to_dict(), indent=self.indent)
    
    def render_replay_diff(self, view: ReplayDiffView) -> str:
        """Render ReplayDiffView as JSON"""
        return json.dumps(view.to_dict(), indent=self.indent)
    
    def render_trace_show(self, view: TraceShowView) -> str:
        """Render TraceShowView as JSON"""
        return json.dumps(view.to_dict(), indent=self.indent)
