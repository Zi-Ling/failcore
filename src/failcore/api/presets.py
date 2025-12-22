# failcore/api/presets.py
"""
Presets API - Unified entry point for all presets

This module re-exports all presets from failcore.presets package.
Implementation is in failcore/presets/ directory.

Three types of presets:
1. validators - precondition/postcondition validators
2. policies - policies (resource access, cost control, etc.)
3. tools - demo tools (minimal set, avoid builtins explosion)

Example:
    >>> from failcore import Session, presets
    >>> session = Session(
    ...     validator=presets.fs_safe(),
    ...     policy=presets.read_only()
    ... )
"""

# Re-export from failcore.presets package
from ..presets import (
    # Validators
    fs_safe,
    net_safe,
    
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
    
    # Policies
    "read_only",
    "safe_write",
    "dangerous_disabled",
    "cost_limit",
    "combine_policies",
    
    # Tools
    "demo_tools",
]
