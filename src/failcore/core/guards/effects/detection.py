# failcore/core/audit/detection.py
"""
Side-Effect Detection - heuristic detection functions

This module provides helper functions for detecting side-effects from
tool names and parameters. These are heuristic predictions used for
pre-execution policy checks and post-execution recording.
"""

from typing import Dict, Any, Optional

from failcore.core.guards.effects.side_effects import SideEffectType


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
    "detect_filesystem_side_effect",
    "detect_network_side_effect",
    "detect_exec_side_effect",
]
