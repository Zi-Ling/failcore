# failcore/core/audit/side_effects.py
"""
Side-Effect Classification System - minimal taxonomy for side-effect boundaries

Defines a fixed, closed set of side-effect categories used for boundary enforcement.
This taxonomy is the foundation for Side-Effect Auditor.
"""

from enum import Enum
from typing import Set


class SideEffectCategory(str, Enum):
    """
    Side-effect category (top-level classification)
    
    Defines the boundary class for side-effects.
    This is a minimal, closed set to avoid infinite expansion.
    """
    FILESYSTEM = "filesystem"  # File system operations (read/write/delete)
    NETWORK = "network"        # Network I/O (outbound/inbound/private)
    EXEC = "exec"              # External execution (subprocess/command)
    PROCESS = "process"        # Process lifecycle (kill/spawn/signal)


class SideEffectType(str, Enum):
    """
    Side-effect type (specific operation within a category)
    
    Defines the specific operation that occurred.
    """
    # Filesystem operations
    FS_READ = "filesystem.read"      # Reading files
    FS_WRITE = "filesystem.write"    # Writing or modifying files
    FS_DELETE = "filesystem.delete"  # Deleting files or directories
    
    # Network operations
    NET_EGRESS = "network.egress"    # Outbound network requests
    NET_INGRESS = "network.ingress"  # Inbound network connections
    NET_PRIVATE = "network.private"  # Accessing private/link-local networks
    
    # Exec operations
    EXEC_SUBPROCESS = "exec.subprocess"  # Subprocess execution
    EXEC_COMMAND = "exec.command"        # Shell command execution
    EXEC_SCRIPT = "exec.script"          # Script invocation
    
    # Process operations
    PROCESS_SPAWN = "process.spawn"  # Spawning new processes
    PROCESS_KILL = "process.kill"    # Killing processes
    PROCESS_SIGNAL = "process.signal"  # Sending signals


# Mapping from category to types
CATEGORY_TYPES: dict[SideEffectCategory, Set[SideEffectType]] = {
    SideEffectCategory.FILESYSTEM: {
        SideEffectType.FS_READ,
        SideEffectType.FS_WRITE,
        SideEffectType.FS_DELETE,
    },
    SideEffectCategory.NETWORK: {
        SideEffectType.NET_EGRESS,
        SideEffectType.NET_INGRESS,
        SideEffectType.NET_PRIVATE,
    },
    SideEffectCategory.EXEC: {
        SideEffectType.EXEC_SUBPROCESS,
        SideEffectType.EXEC_COMMAND,
        SideEffectType.EXEC_SCRIPT,
    },
    SideEffectCategory.PROCESS: {
        SideEffectType.PROCESS_SPAWN,
        SideEffectType.PROCESS_KILL,
        SideEffectType.PROCESS_SIGNAL,
    },
}


def get_types_for_category(category: SideEffectCategory) -> Set[SideEffectType]:
    """
    Get all side-effect types for a category
    
    Args:
        category: Side-effect category
    
    Returns:
        Set of side-effect types for the category
    """
    return CATEGORY_TYPES.get(category, set())


def get_category_for_type(side_effect_type: SideEffectType) -> SideEffectCategory:
    """
    Get category for a side-effect type
    
    Args:
        side_effect_type: Side-effect type
    
    Returns:
        Side-effect category
    """
    category_prefix = side_effect_type.value.split(".", 1)[0]
    return SideEffectCategory(category_prefix)


__all__ = [
    "SideEffectCategory",
    "SideEffectType",
    "CATEGORY_TYPES",
    "get_types_for_category",
    "get_category_for_type",
]
