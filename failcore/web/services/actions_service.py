# failcore/web/services/actions_service.py
"""
Action registry and capability gating.

Actions are the extensible UI operations (Generate Report, Audit, Replay, etc.)
"""

from dataclasses import dataclass
from typing import Literal, Optional, List
import os


ActionScope = Literal["global", "run", "trace"]
ActionResult = Literal["job", "download", "navigate"]


@dataclass
class Action:
    """
    Represents a UI action (button) that triggers an operation.
    
    Actions are registered centrally and rendered dynamically in templates.
    This enables adding new commands without changing UI structure.
    """
    id: str                          # Unique identifier: "report.generate"
    label: str                       # Button text: "Generate Report"
    scope: ActionScope               # Where it appears: run/trace/global
    method: str                      # HTTP method: GET/POST
    endpoint: str                    # API endpoint: /api/actions/report
    result: ActionResult             # What happens after: job/download/navigate
    icon: Optional[str] = None       # Icon class/emoji
    danger: bool = False             # Require confirmation
    capability: Optional[str] = None # Required capability flag
    description: Optional[str] = None


class ActionsService:
    """
    Central registry for all UI actions.
    
    New commands are added here without changing templates.
    """
    
    def __init__(self):
        self._actions: List[Action] = []
        self._capabilities = self._load_capabilities()
        self._register_default_actions()
    
    def _load_capabilities(self) -> dict:
        """Load capability flags from environment."""
        return {
            "generate": os.getenv("WEB_ALLOW_GENERATE", "true").lower() == "true",
            "replay": os.getenv("WEB_ALLOW_REPLAY", "false").lower() == "true",
            "run": os.getenv("WEB_ALLOW_RUN", "false").lower() == "true",
            "delete": os.getenv("WEB_ALLOW_DELETE", "false").lower() == "true",
        }
    
    def _register_default_actions(self):
        """Register built-in actions."""
        # Safe operations (always allowed if capability enabled)
        self.register(Action(
            id="report.generate",
            label="Generate Report",
            scope="run",
            method="POST",
            endpoint="/api/actions/report",
            result="job",
            icon="📊",
            capability="generate",
            description="Generate HTML execution report",
        ))
        
        self.register(Action(
            id="audit.generate",
            label="Generate Audit",
            scope="run",
            method="POST",
            endpoint="/api/actions/audit",
            result="job",
            icon="🔍",
            capability="generate",
            description="Generate security audit report",
        ))
        
        self.register(Action(
            id="trace.export",
            label="Export Trace",
            scope="run",
            method="GET",
            endpoint="/api/actions/export",
            result="download",
            icon="💾",
            capability="generate",
            description="Download trace as JSON",
        ))
        
        # Medium-risk operations (gated by capability)
        self.register(Action(
            id="replay.run",
            label="Replay Run",
            scope="run",
            method="POST",
            endpoint="/api/actions/replay",
            result="job",
            icon="🔄",
            danger=True,
            capability="replay",
            description="Replay this execution with same inputs",
        ))
        
        # High-risk operations (gated by capability)
        self.register(Action(
            id="run.delete",
            label="Delete Run",
            scope="run",
            method="DELETE",
            endpoint="/api/actions/delete",
            result="navigate",
            icon="🗑",
            danger=True,
            capability="delete",
            description="Permanently delete this run and trace",
        ))
    
    def register(self, action: Action):
        """Register a new action."""
        self._actions.append(action)
    
    def get_actions(self, scope: ActionScope, check_capabilities: bool = True) -> List[Action]:
        """Get actions for a specific scope, filtered by capabilities."""
        actions = [a for a in self._actions if a.scope == scope]
        
        if check_capabilities:
            # Filter by capability flags
            actions = [
                a for a in actions
                if a.capability is None or self._capabilities.get(a.capability, False)
            ]
        
        return actions
    
    def get_action(self, action_id: str) -> Optional[Action]:
        """Get a specific action by ID."""
        for action in self._actions:
            if action.id == action_id:
                return action
        return None
    
    def is_allowed(self, action_id: str) -> bool:
        """Check if an action is allowed based on capabilities."""
        action = self.get_action(action_id)
        if not action:
            return False
        if action.capability is None:
            return True
        return self._capabilities.get(action.capability, False)
    
    def get_tool_metadata(self, tool_name: str) -> Optional[dict]:
        """
        Get tool metadata (risk_level, side_effect) for a tool.
        
        Args:
            tool_name: Tool name
        
        Returns:
            Dictionary with metadata or None if not found:
            {
                "risk_level": "low" | "medium" | "high",
                "side_effect": "read" | "fs" | "network" | "exec" | None,
                "default_action": "allow" | "warn" | "block"
            }
        """
        try:
            from failcore.core.tools.registry import get_tool_registry
            from failcore.core.tools.metadata import DEFAULT_METADATA_PROFILES
            
            # First try to get from registry
            registry = get_tool_registry()
            if registry:
                tool_info = registry.describe(tool_name)
                if tool_info and "risk_level" in tool_info:
                    return {
                        "risk_level": tool_info.get("risk_level", "medium"),
                        "side_effect": tool_info.get("side_effect"),
                        "default_action": tool_info.get("default_action", "warn"),
                    }
            
            # Fallback to default metadata profiles
            if tool_name in DEFAULT_METADATA_PROFILES:
                metadata = DEFAULT_METADATA_PROFILES[tool_name]
                return {
                    "risk_level": metadata.risk_level.value,
                    "side_effect": metadata.side_effect.value if metadata.side_effect else None,
                    "default_action": metadata.default_action.value,
                }
            
            # Default fallback
            return {
                "risk_level": "medium",
                "side_effect": None,
                "default_action": "warn",
            }
        except Exception:
            # If anything fails, return safe defaults
            return {
                "risk_level": "medium",
                "side_effect": None,
                "default_action": "warn",
            }


# Global singleton
_service = ActionsService()


def get_actions_service() -> ActionsService:
    """Get the global actions service."""
    return _service


__all__ = ["Action", "ActionsService", "get_actions_service"]
