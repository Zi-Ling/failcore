# failcore/core/validate/templates.py
"""
Policy Presets: Pre-configured policy templates.

This module provides policy templates, NOT validation logic.
Presets are simply PolicyV1 configurations that can be:
- Used directly
- Extended/modified
- Distributed as part of a community rule repository

Design principles:
- Presets are data (PolicyV1 objects), not code
- Validation logic lives in builtin, not presets
- Presets define configuration, not behavior
- Easy to serialize, review, and version control
"""

from __future__ import annotations

from typing import Dict, Optional

from .contracts import (
    Policy,
    ValidatorConfig,
    EnforcementMode,
    OverrideConfig,
)


def default_safe_policy() -> Policy:
    """
    Default safe policy for general use.
    
    Enables:
    - Security: Path traversal protection
    - Network: SSRF protection
    - Resource: Basic limits
    
    Mode: BLOCK (strict enforcement)
    """
    return Policy(
        version="v1",
        validators={
            "security_path_traversal": ValidatorConfig(
                id="security_path_traversal",
                domain="security",
                enabled=True,
                enforcement=EnforcementMode.BLOCK,
                priority=30,
                config={
                    "path_params": ["path", "file_path", "relative_path"],
                    "sandbox_root": None,
                },
            ),
            "network_ssrf": ValidatorConfig(
                id="network_ssrf",
                domain="network",
                enabled=True,
                enforcement=EnforcementMode.BLOCK,
                priority=40,
                config={
                    "url_params": ["url", "uri", "endpoint"],
                    "block_internal": True,
                    "allowed_schemes": ["http", "https"],
                    "allowed_ports": [80, 443],
                    "forbid_userinfo": True,
                    "allowlist": None,
                },
            ),
            "resource_file_size": ValidatorConfig(
                id="resource_file_size",
                domain="resource",
                enabled=True,
                enforcement=EnforcementMode.WARN,
                priority=50,
                config={
                    "param_name": "path",
                    "max_bytes": 100 * 1024 * 1024,  # 100MB
                },
            ),
        },
        global_override=OverrideConfig(
            enabled=False,
            require_token=True,
        ),
        metadata={
            "name": "default_safe",
            "description": "Default safe policy for general use",
            "version": "1.0.0",
        },
    )


def fs_safe_policy(sandbox_root: Optional[str] = None) -> Policy:
    """
    Filesystem-focused safety policy.
    
    Enables:
    - Security: Path traversal protection with sandbox
    - Resource: File size limits
    
    Mode: BLOCK
    
    Args:
        sandbox_root: Optional sandbox root directory
    """
    return Policy(
        version="v1",
        validators={
            "security_path_traversal": ValidatorConfig(
                id="security_path_traversal",
                domain="security",
                enabled=True,
                enforcement=EnforcementMode.BLOCK,
                priority=30,
                config={
                    "path_params": ["path", "file_path", "relative_path", "output_path", "dst"],
                    "sandbox_root": sandbox_root,
                },
            ),
            "resource_file_size": ValidatorConfig(
                id="resource_file_size",
                domain="resource",
                enabled=True,
                enforcement=EnforcementMode.BLOCK,
                priority=50,
                config={
                    "param_name": "path",
                    "max_bytes": 50 * 1024 * 1024,  # 50MB
                },
            ),
        },
        metadata={
            "name": "fs_safe",
            "description": "Filesystem safety policy with sandbox protection",
            "version": "1.0.0",
        },
    )


def net_safe_policy(allowlist: Optional[list] = None) -> Policy:
    """
    Network-focused safety policy.
    
    Enables:
    - Network: Strict SSRF protection
    
    Mode: BLOCK
    
    Args:
        allowlist: Optional domain/IP allowlist
    """
    return Policy(
        version="v1",
        validators={
            "network_ssrf": ValidatorConfig(
                id="network_ssrf",
                domain="network",
                enabled=True,
                enforcement=EnforcementMode.BLOCK,
                priority=40,
                config={
                    "url_params": ["url", "uri", "endpoint"],
                    "block_internal": True,
                    "allowed_schemes": ["http", "https"],
                    "allowed_ports": [80, 443, 8080, 8443],
                    "forbid_userinfo": True,
                    "allowlist": allowlist,
                },
            ),
        },
        metadata={
            "name": "net_safe",
            "description": "Network safety policy with SSRF protection",
            "version": "1.0.0",
        },
    )


def shadow_mode_policy() -> Policy:
    """
    Shadow mode policy for observation without blocking.
    
    Enables all builtin in SHADOW mode for safe rollout.
    
    Use this to:
    - Test new policies without breaking production
    - Observe validation decisions
    - Collect data for tuning
    """
    return Policy(
        version="v1",
        validators={
            "security_path_traversal": ValidatorConfig(
                id="security_path_traversal",
                domain="security",
                enabled=True,
                enforcement=EnforcementMode.SHADOW,
                priority=30,
                config={},
            ),
            "network_ssrf": ValidatorConfig(
                id="network_ssrf",
                domain="network",
                enabled=True,
                enforcement=EnforcementMode.SHADOW,
                priority=40,
                config={},
            ),
            "resource_file_size": ValidatorConfig(
                id="resource_file_size",
                domain="resource",
                enabled=True,
                enforcement=EnforcementMode.SHADOW,
                priority=50,
                config={},
            ),
        },
        metadata={
            "name": "shadow_mode",
            "description": "Shadow mode policy for safe observation",
            "version": "1.0.0",
        },
    )


def permissive_policy() -> Policy:
    """
    Permissive policy with minimal restrictions.
    
    Only enables critical security checks in WARN mode.
    
    Use this for:
    - Development environments
    - Trusted workflows
    - Gradual policy adoption
    """
    return Policy(
        version="v1",
        validators={
            "security_path_traversal": ValidatorConfig(
                id="security_path_traversal",
                domain="security",
                enabled=True,
                enforcement=EnforcementMode.WARN,
                priority=30,
                config={},
            ),
        },
        metadata={
            "name": "permissive",
            "description": "Permissive policy for development",
            "version": "1.0.0",
        },
    )


# Preset registry
POLICY_PRESETS: Dict[str, Policy] = {
    "default_safe": default_safe_policy(),
    "fs_safe": fs_safe_policy(),
    "net_safe": net_safe_policy(),
    "shadow_mode": shadow_mode_policy(),
    "permissive": permissive_policy(),
}


def get_preset(name: str) -> Optional[Policy]:
    """
    Get policy preset by name.
    
    Args:
        name: Preset name (e.g., 'default_safe', 'fs_safe')
    
    Returns:
        PolicyV1 instance or None if not found
    """
    return POLICY_PRESETS.get(name)


def list_presets() -> list[str]:
    """
    List all available preset names.
    
    Returns:
        List of preset names
    """
    return list(POLICY_PRESETS.keys())


__all__ = [
    "default_safe_policy",
    "fs_safe_policy",
    "net_safe_policy",
    "shadow_mode_policy",
    "permissive_policy",
    "get_preset",
    "list_presets",
    "POLICY_PRESETS",
]
