# failcore/core/config/boundaries.py
"""
Side-Effect Boundary Presets - default boundaries and preset mappings

Provides predefined boundary configurations for common use cases.
"""

from typing import Dict, Optional

from failcore.core.guards.effects.boundary import SideEffectBoundary
from failcore.core.guards.effects.side_effects import SideEffectCategory, SideEffectType


# Preset boundary configurations
PRESETS: Dict[str, SideEffectBoundary] = {
    # Strict: Only allow read operations
    "strict": SideEffectBoundary(
        allowed_categories={SideEffectCategory.FILESYSTEM},
        allowed_types={SideEffectType.FS_READ},
        blocked_categories={SideEffectCategory.NETWORK, SideEffectCategory.EXEC, SideEffectCategory.PROCESS},
    ),
    
    # Permissive: Allow read/write filesystem and outbound network
    "permissive": SideEffectBoundary(
        allowed_categories={SideEffectCategory.FILESYSTEM, SideEffectCategory.NETWORK},
        allowed_types={
            SideEffectType.FS_READ,
            SideEffectType.FS_WRITE,
            SideEffectType.NET_EGRESS,
        },
        blocked_categories={SideEffectCategory.EXEC, SideEffectCategory.PROCESS},
    ),
    
    # Read-only: Only filesystem reads, no writes
    "read_only": SideEffectBoundary(
        allowed_categories={SideEffectCategory.FILESYSTEM},
        allowed_types={SideEffectType.FS_READ},
        blocked_types={SideEffectType.FS_WRITE, SideEffectType.FS_DELETE},
    ),
    
    # Network-only: Only outbound network requests
    "network_only": SideEffectBoundary(
        allowed_categories={SideEffectCategory.NETWORK},
        allowed_types={SideEffectType.NET_EGRESS},
        blocked_categories={SideEffectCategory.FILESYSTEM, SideEffectCategory.EXEC, SideEffectCategory.PROCESS},
    ),
    
    # No restrictions: All categories allowed (default for backwards compatibility)
    "none": SideEffectBoundary(
        allowed_categories={
            SideEffectCategory.FILESYSTEM,
            SideEffectCategory.NETWORK,
            SideEffectCategory.EXEC,
            SideEffectCategory.PROCESS,
        },
    ),
}


def get_boundary(preset: Optional[str] = None) -> SideEffectBoundary:
    """
    Get boundary configuration by preset name
    
    Args:
        preset: Preset name (e.g., "strict", "permissive", "read_only")
                 If None, returns "none" preset (all allowed)
    
    Returns:
        SideEffectBoundary instance
    """
    if preset is None:
        preset = "none"
    
    return PRESETS.get(preset, PRESETS["none"])


def list_presets() -> list[str]:
    """
    List available preset names
    
    Returns:
        List of preset names
    """
    return list(PRESETS.keys())


__all__ = [
    "PRESETS",
    "get_boundary",
    "list_presets",
]
