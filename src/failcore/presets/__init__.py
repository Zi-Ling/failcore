# failcore/presets/__init__.py
"""
Presets - Turn complexity into switches

This package provides ready-to-use presets for:
- Validators (fs_safe, net_safe)
- Policies (read_only, safe_write, dangerous_disabled, cost_limit)
- Tools (demo_tools)

All presets are framework-agnostic and reusable.
"""

from .validators import fs_safe, net_safe
from .policies import (
    read_only,
    safe_write,
    dangerous_disabled,
    cost_limit,
    combine_policies,
)
from .tools import demo_tools

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

