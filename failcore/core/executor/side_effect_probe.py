# failcore/core/executor/side_effect_probe.py
"""
Side-Effect Probe - runtime side-effect detection and recording

This module captures "what side-effects occurred" during tool execution.
It does NOT make judgments, does NOT block, does NOT throw errors.
It only records facts that can be used later for audit/enforcement.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

from ..audit.side_effects import SideEffectType
from ..trace.events import SideEffectInfo, EventType


@dataclass
class SideEffectEvent:
    """
    Side-effect event record
    
    Represents a single side-effect that occurred during execution.
    """
    type: SideEffectType
    target: Optional[str] = None
    tool: Optional[str] = None
    step_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_side_effect_info(self) -> SideEffectInfo:
        """Convert to SideEffectInfo for trace event"""
        from ..audit.side_effects import get_category_for_type
        
        if isinstance(self.type, SideEffectType):
            category = get_category_for_type(self.type).value
            type_str = self.type.value
        else:
            category = str(self.type).split(".", 1)[0] if "." in str(self.type) else None
            type_str = str(self.type)
        
        return SideEffectInfo(
            type=type_str,
            target=self.target,
            category=category,
            tool=self.tool,
            step_id=self.step_id,
            metadata=self.metadata,
        )


class SideEffectProbe:
    """
    Runtime side-effect probe
    
    Detects and records side-effects during tool execution.
    This is a "black box recorder" - only observes and records, never interferes.
    """
    
    def __init__(self, emit: Optional[Callable] = None):
        """
        Initialize side-effect probe
        
        Args:
            emit: Optional event emitter function (for recording events)
        """
        self.emit = emit or (lambda _: None)
        self._events: List[SideEffectEvent] = []
    
    def record(
        self,
        side_effect_type: SideEffectType,
        target: Optional[str] = None,
        tool: Optional[str] = None,
        step_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a side-effect occurrence
        
        This method records what happened - it does NOT judge or block.
        
        Args:
            side_effect_type: Type of side-effect that occurred
            target: Target of the side-effect (e.g., file path, hostname)
            tool: Tool name that caused the side-effect
            step_id: Step ID where side-effect occurred
            metadata: Additional metadata about the side-effect
        """
        event = SideEffectEvent(
            type=side_effect_type,
            target=target,
            tool=tool,
            step_id=step_id,
            metadata=metadata or {},
        )
        
        self._events.append(event)
        
        # Emit trace event if emitter is available
        if self.emit:
            self._emit_side_effect_applied(event)
    
    def _emit_side_effect_applied(self, event: SideEffectEvent) -> None:
        """
        Emit SIDE_EFFECT_APPLIED trace event
        
        Args:
            event: Side-effect event to emit
        """
        side_effect_info = event.to_side_effect_info()
        
        # Build event structure
        event_data = {
            "type": EventType.SIDE_EFFECT_APPLIED.value,
            "data": {
                "side_effect": {
                    "type": side_effect_info.type,
                    "target": side_effect_info.target,
                    "category": side_effect_info.category,
                    "tool": side_effect_info.tool,
                    "step_id": side_effect_info.step_id,
                    "metadata": side_effect_info.metadata,
                }
            }
        }
        
        # Emit event (format depends on emitter interface)
        self.emit(event_data)
    
    def get_events(self) -> List[SideEffectEvent]:
        """
        Get all recorded side-effect events
        
        Returns:
            List of side-effect events
        """
        return self._events.copy()
    
    def clear(self) -> None:
        """Clear all recorded events"""
        self._events.clear()


# Helper functions for detecting side-effects from tool execution
def detect_filesystem_side_effect(
    tool: str,
    params: Dict[str, Any],
    operation: str = "read",  # "read", "write", "delete"
) -> Optional[SideEffectType]:
    """
    Detect filesystem side-effect from tool and parameters
    
    Args:
        tool: Tool name
        params: Tool parameters
        operation: Operation type ("read", "write", "delete")
    
    Returns:
        Side-effect type if detected, None otherwise
    """
    # Check if tool is filesystem-related (simple heuristic)
    fs_keywords = ("file", "dir", "path", "read", "write", "delete", "create", "mkdir")
    if any(keyword in tool.lower() for keyword in fs_keywords):
        # Check for path parameter
        path_param = params.get("path") or params.get("file") or params.get("filepath")
        if path_param:
            if operation == "read":
                return SideEffectType.FS_READ
            elif operation == "write":
                return SideEffectType.FS_WRITE
            elif operation == "delete":
                return SideEffectType.FS_DELETE
    
    return None


def detect_network_side_effect(
    tool: str,
    params: Dict[str, Any],
    direction: str = "egress",  # "egress", "ingress", "private"
) -> Optional[SideEffectType]:
    """
    Detect network side-effect from tool and parameters
    
    Args:
        tool: Tool name
        params: Tool parameters
        direction: Network direction ("egress", "ingress", "private")
    
    Returns:
        Side-effect type if detected, None otherwise
    """
    # Check if tool is network-related
    network_keywords = ("http", "request", "fetch", "url", "host", "api", "client")
    if any(keyword in tool.lower() for keyword in network_keywords):
        # Check for URL/host parameter
        url_param = params.get("url") or params.get("host") or params.get("hostname")
        if url_param:
            if direction == "egress":
                return SideEffectType.NET_EGRESS
            elif direction == "ingress":
                return SideEffectType.NET_INGRESS
            elif direction == "private":
                return SideEffectType.NET_PRIVATE
    
    return None


def detect_exec_side_effect(
    tool: str,
    params: Dict[str, Any],
) -> Optional[SideEffectType]:
    """
    Detect exec side-effect from tool and parameters
    
    Args:
        tool: Tool name
        params: Tool parameters
    
    Returns:
        Side-effect type if detected, None otherwise
    """
    # Check if tool is exec-related
    exec_keywords = ("exec", "run", "command", "shell", "subprocess", "script")
    if any(keyword in tool.lower() for keyword in exec_keywords):
        # Check for command parameter
        command_param = params.get("command") or params.get("cmd") or params.get("script")
        if command_param:
            if "subprocess" in tool.lower():
                return SideEffectType.EXEC_SUBPROCESS
            elif "script" in tool.lower():
                return SideEffectType.EXEC_SCRIPT
            else:
                return SideEffectType.EXEC_COMMAND
    
    return None


__all__ = [
    "SideEffectEvent",
    "SideEffectProbe",
    "detect_filesystem_side_effect",
    "detect_network_side_effect",
    "detect_exec_side_effect",
]
