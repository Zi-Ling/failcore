# failcore/api/presets.py
"""
Presets API - Unified entry point for all presets

This module re-exports all presets from failcore.presets package.
Implementation is in failcore/presets/ directory.

Three types of presets:
1. builtin - precondition/postcondition builtin
2. policies - policies (resource access, cost control, etc.)
3. tools - demo tools (minimal set, avoid builtins explosion)

"""

# Re-export from failcore.presets package
from ..presets import (
    # Validators
    fs_safe,
    net_safe,
    fs_safe_sandbox,
    resource_limited,
    combined_safe,
    
    # Policies
    read_only,
    safe_write,
    dangerous_disabled,
    cost_limit,
    combine_policies,
    
    # Tools
    demo_tools,
)

__all__ = [
    # Validators
    "fs_safe",
    "net_safe",
    "fs_safe_sandbox",  # Deprecated, use fs_safe(strict=True)
    "resource_limited",  # v0.1.3+
    "combined_safe",  # v0.1.3+
    
    # Policies
    "read_only",
    "safe_write",
    "dangerous_disabled",
    "cost_limit",
    "combine_policies",
    
    # Tools
    "demo_tools",
]
