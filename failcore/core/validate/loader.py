# failcore/core/validate/loader.py
"""
Policy Loader: Policy-as-Data implementation with three-layer merge.

This module provides:
- Core layer (pure, no I/O):
  - parse_policy_from_str(content, format) -> Policy: Parse policy from string
  - parse_policy_from_dict(data) -> Policy: Parse policy from dict
  - serialize_policy_to_str(policy, format) -> str: Serialize policy to string
  - serialize_policy_to_dict(policy) -> dict: Serialize policy to dict
- API layer (with I/O):
  - load_policy(path) -> Policy: Load policy from YAML/JSON file
  - dump_policy(policy) -> str: Serialize policy to YAML/JSON  
  - save_policy(policy, path) -> None: Save policy to file
  - merge_policies(active, shadow, breakglass) -> Policy: Three-layer merge
  - load_merged_policy() -> Policy: Load from .failcore/validate/ directory

Design principles:
- Policy is first-class citizen (versionable, diffable, reviewable)
- YAML only for configuration, not logic
- Strict validation on load
- Clear merge rules for three-layer system
- Core layer is I/O-free for extractability (WASM, Rust, mobile, etc.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union, Dict, Any
from datetime import datetime
import yaml
import json

from .contracts import Policy, ValidatorConfig, EnforcementMode, OverrideConfig


def _validate_global_override(override: OverrideConfig, policy_name: str = "policy") -> None:
    """
    Validate global override configuration.
    
    Strict validation: if enabled=True, expires_at must be set with timezone.
    
    Args:
        override: OverrideConfig to validate
        policy_name: Policy name for error messages (active/shadow/breakglass)
    
    Raises:
        ValueError: If override is enabled but expires_at is missing or invalid
    """
    if not override.enabled:
        return  # No validation needed if disabled
    
    if not override.expires_at:
        raise ValueError(
            f"{policy_name.capitalize()} policy: global_override.enabled=true requires expires_at to be set. "
            f"Emergency overrides cannot be permanent. Please set expires_at with ISO8601 format (with timezone)."
        )
    
    # Validate expires_at format (must be ISO8601 with timezone)
    try:
        expiry_str = override.expires_at.replace('Z', '+00:00')
        expiry = datetime.fromisoformat(expiry_str)
        
        # Check if timezone is present (ISO8601 requires timezone for safety)
        if expiry.tzinfo is None:
            raise ValueError(
                f"{policy_name.capitalize()} policy: global_override.expires_at must include timezone "
                f"(ISO8601 format, e.g., '2024-01-15T00:00:00+00:00' or '2024-01-15T00:00:00Z')."
            )
        
        # Check if already expired
        if datetime.now(expiry.tzinfo) > expiry:
            raise ValueError(
                f"{policy_name.capitalize()} policy: global_override.expires_at is in the past: {override.expires_at}"
            )
            
    except ValueError as e:
        # Re-raise our custom validation errors
        raise e
    except Exception as e:
        raise ValueError(
            f"{policy_name.capitalize()} policy: global_override.expires_at has invalid format: {override.expires_at}. "
            f"Expected ISO8601 format with timezone (e.g., '2024-01-15T00:00:00+00:00'). Error: {e}"
        ) from e


# ============================================================================
# API layer: I/O functions (use core layer for parsing)
# ============================================================================

def load_policy(path: Union[str, Path]) -> Policy:
    """
    Load policy from YAML or JSON file (API layer, with I/O).
    
    This function performs file I/O and delegates parsing to parse_policy_from_str().
    For core extraction, use parse_policy_from_str() or parse_policy_from_dict() instead.
    
    Args:
        path: Path to policy file (.yaml, .yml, or .json)
    
    Returns:
        Policy object
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is invalid
    
    Example:
        >>> policy = load_policy(".failcore/validate/active.yaml")
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")
    
    content = path.read_text(encoding="utf-8")
    
    # Determine format from extension
    if path.suffix in (".yaml", ".yml"):
        format = "yaml"
    elif path.suffix == ".json":
        format = "json"
    else:
        raise ValueError(f"Unsupported policy file format: {path.suffix}")
    
    # Use core layer for parsing (I/O-free)
    policy = parse_policy_from_str(content, format=format)
    
    # Validate with policy name from file stem
    policy_name = path.stem  # active, shadow, breakglass
    _validate_global_override(policy.global_override, policy_name)
    
    return policy


def dump_policy(policy: Policy, format: str = "yaml") -> str:
    """
    Serialize policy to YAML or JSON string (API layer, convenience function).
    
    This function delegates to serialize_policy_to_str().
    For core extraction, use serialize_policy_to_str() directly.
    
    Args:
        policy: Policy object
        format: Output format ("yaml" or "json")
    
    Returns:
        Serialized policy string
    """
    return serialize_policy_to_str(policy, format=format)


def save_policy(policy: Policy, path: Union[str, Path], format: Optional[str] = None) -> None:
    """
    Save policy to file.
    
    Args:
        policy: Policy object
        path: Output file path
        format: File format ("yaml" or "json"). If None, inferred from extension.
    """
    path = Path(path)
    
    if format is None:
        if path.suffix in (".yaml", ".yml"):
            format = "yaml"
        elif path.suffix == ".json":
            format = "json"
        else:
            format = "yaml"
    
    # Use core layer for serialization (I/O-free)
    content = serialize_policy_to_str(policy, format=format)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def get_policy_dir(project_root: Optional[Path] = None) -> Path:
    """
    Get .failcore/validate/ directory path.
    
    Args:
        project_root: Project root directory. If None, uses current working directory.
    
    Returns:
        Path to .failcore/validate/ directory
    """
    if project_root is None:
        project_root = Path.cwd()
    
    return project_root / ".failcore" / "validate"


def ensure_policy_dir(project_root: Optional[Path] = None) -> Path:
    """
    Ensure .failcore/validate/ directory exists.
    
    Args:
        project_root: Project root directory
    
    Returns:
        Path to .failcore/validate/ directory
    """
    policy_dir = get_policy_dir(project_root)
    policy_dir.mkdir(parents=True, exist_ok=True)
    return policy_dir


# ============================================================================
# Three-layer policy merge (Step 4)
# ============================================================================

def merge_policies(
    active: Policy,
    shadow: Optional[Policy] = None,
    breakglass: Optional[Policy] = None,
) -> Policy:
    """
    Merge three-layer policy system.
    
    Merge order:
    1. Start with active.yaml (base)
    2. Apply shadow.yaml overlay (convert all enforcement to SHADOW)
    3. Apply breakglass.yaml overlay (override + exceptions only)
    
    Args:
        active: Active policy (required)
        shadow: Shadow policy (optional, converts to SHADOW mode)
        breakglass: Breakglass policy (optional, override only)
    
    Returns:
        Merged Policy object
    """
    merged = active.model_copy(deep=True)
    
    if shadow:
        merged = _apply_shadow_overlay(merged, shadow)
    
    if breakglass:
        merged = _apply_breakglass_overlay(merged, breakglass)
    
    return merged


def _apply_shadow_overlay(base: Policy, shadow: Policy) -> Policy:
    """
    Apply shadow overlay: Convert all enforcement to SHADOW mode.
    
    Shadow overlay principles:
    - Only changes enforcement mode to SHADOW (observation only)
    - Does not add/remove validators (strictly enforced)
    - Does not change validator configuration
    - Does not change validator logic
    
    Shadow is not another policy - it's an execution mode variant of active.
    """
    result = base.model_copy(deep=True)
    
    # Validate: shadow must have same validators as base
    if set(shadow.validators.keys()) != set(result.validators.keys()):
        raise ValueError(
            "Shadow policy must have the same validators as active policy. "
            "Shadow mode cannot introduce new rules or remove existing ones."
        )
    
    # Apply shadow: only change enforcement mode
    for validator_id, shadow_config in shadow.validators.items():
        if validator_id in result.validators:
            # Only enforcement mode is changed
            result.validators[validator_id].enforcement = EnforcementMode.SHADOW
            # Config, domain, priority remain unchanged
    
    return result


def _apply_breakglass_overlay(base: Policy, breakglass: Policy) -> Policy:
    """
    Apply breakglass overlay: Emergency override only (strict restrictions).
    
    Breakglass overlay can only:
    - Enable global override
    - Add exceptions to existing validators (must have expires_at)
    - Override enforcement mode (temporarily, only for existing validators)
    
    Breakglass cannot:
    - Add new validators (strictly enforced)
    - Change validator configuration
    - Change validator domain / priority / logic
    - Remove validators
    - Add long-term exceptions (must have expires_at)
    """
    result = base.model_copy(deep=True)
    
    # Apply global override (with strict validation)
    # Note: breakglass.global_override was already validated in load_policy(),
    # but we validate again here for extra safety (breakglass requires highest scrutiny).
    # This is intentional duplication for defense-in-depth.
    if breakglass.global_override.enabled:
        _validate_global_override(breakglass.global_override, "breakglass")
        result.global_override = breakglass.global_override.model_copy(deep=True)
    
    # Apply exceptions and overrides (only to existing validators)
    for validator_id, breakglass_config in breakglass.validators.items():
        if validator_id not in result.validators:
            # Strict: breakglass cannot add new validators
            raise ValueError(
                f"Breakglass policy cannot add new validator '{validator_id}'. "
                f"Breakglass can only add exceptions or override enforcement for existing validators."
            )
        
        base_config = result.validators[validator_id]
        
        # Add exceptions (validate they have expires_at)
        if breakglass_config.exceptions:
            for exc in breakglass_config.exceptions:
                if not exc.expires_at:
                    raise ValueError(
                        f"Breakglass exception for '{validator_id}' must have expires_at. "
                        f"Emergency overrides cannot be permanent."
                    )
            base_config.exceptions.extend(breakglass_config.exceptions)
        
        # Override enforcement mode (temporary downgrade only)
        if breakglass_config.enforcement != EnforcementMode.BLOCK:
            base_config.enforcement = breakglass_config.enforcement
        
        # Enable override flag
        if breakglass_config.allow_override:
            base_config.allow_override = True
        
        # Strict: cannot change config
        if breakglass_config.config and breakglass_config.config != base_config.config:
            # Allow if breakglass config is empty or same
            pass  # Config changes are ignored (breakglass cannot modify config)
    
    return result


def load_merged_policy(
    project_root: Optional[Path] = None,
    use_shadow: bool = False,
    use_breakglass: bool = False,
    auto_init: bool = True,
) -> Policy:
    """
    Load and merge policies from .failcore/validate/ directory.
    
    This is the main entry point for loading policies.
    If active.yaml doesn't exist and auto_init=True, it will automatically
    initialize the policy directory with template files.
    
    Args:
        project_root: Project root directory
        use_shadow: If True, apply shadow.yaml overlay
        use_breakglass: If True, apply breakglass.yaml overlay
        auto_init: If True, automatically initialize policy files if missing (default: True)
    
    Returns:
        Merged Policy object
    
    Raises:
        FileNotFoundError: If active.yaml doesn't exist and auto_init=False
        ValueError: If breakglass policy violates restrictions
    
    Example:
        >>> # Auto-initialize on first run
        >>> policy = load_merged_policy()
        
        >>> # Load with shadow mode
        >>> policy = load_merged_policy(use_shadow=True)
        
        >>> # Load with breakglass (emergency override)
        >>> policy = load_merged_policy(use_breakglass=True)
    """
    policy_dir = get_policy_dir(project_root)
    
    # Auto-initialize if needed (idempotent)
    active_path = policy_dir / "active.yaml"
    if not active_path.exists():
        if auto_init:
            ensure_policy_files(project_root)
        else:
            raise FileNotFoundError(
                f"Active policy not found: {active_path}\n"
                f"Run: from failcore.core.validate.loader import ensure_policy_files; ensure_policy_files()\n"
                f"Or set auto_init=True when calling load_merged_policy()"
            )
    
    # Load active (required)
    active = load_policy(active_path)
    
    # Load shadow (optional, must be derived from active)
    shadow = None
    if use_shadow:
        shadow_path = policy_dir / "shadow.yaml"
        if shadow_path.exists():
            shadow = load_policy(shadow_path)
            # Validate shadow is derived from active (same validators)
            if set(shadow.validators.keys()) != set(active.validators.keys()):
                raise ValueError(
                    "shadow.yaml must have the same validators as active.yaml. "
                    "Shadow mode cannot add or remove validators."
                )
    
    # Load breakglass (optional, strict restrictions)
    breakglass = None
    if use_breakglass:
        breakglass_path = policy_dir / "breakglass.yaml"
        if breakglass_path.exists():
            breakglass = load_policy(breakglass_path)
            # Validate breakglass restrictions
            for validator_id, breakglass_config in breakglass.validators.items():
                # 1. Cannot add new validators
                if validator_id not in active.validators:
                    raise ValueError(
                        f"Breakglass cannot add new validator '{validator_id}'. "
                        f"Breakglass can only add exceptions or override enforcement for existing validators."
                    )
                
                # 2. Exceptions must have expires_at (cannot be permanent)
                for exc in breakglass_config.exceptions:
                    if not exc.expires_at:
                        raise ValueError(
                            f"Breakglass exception for validator '{validator_id}' (rule: {exc.rule_id}) "
                            f"must have expires_at. Emergency overrides cannot be permanent."
                        )
                    
                    # Check if already expired
                    if exc.is_expired():
                        raise ValueError(
                            f"Breakglass exception for validator '{validator_id}' (rule: {exc.rule_id}) "
                            f"has already expired: {exc.expires_at}"
                        )
    
    # Merge (will raise ValueError if breakglass violations)
    return merge_policies(active, shadow=shadow, breakglass=breakglass)


def init_policy_files(project_root: Optional[Path] = None, force: bool = False) -> None:
    """
    Initialize policy files in .failcore/validate/ directory.
    
    This is an idempotent operation:
    - Directory exists → No action
    - File exists → No override (unless force=True)
    
    Creates:
    - active.yaml: Main policy (required, from default_safe_policy)
    - shadow.yaml: Shadow mode overlay (derived from active, enforcement=SHADOW)
    - breakglass.yaml: Emergency override template (empty, disabled by default)
    
    Args:
        project_root: Project root directory
        force: If True, overwrite existing files (default: False)
    
    Note:
        This function can be safely added to version control.
        Files are only created if they don't exist (unless force=True).
    """
    from datetime import datetime
    
    policy_dir = ensure_policy_dir(project_root)
    
    # Import presets
    from .templates import default_safe_policy
    
    # 1. Create active.yaml (main policy, required)
    active_path = policy_dir / "active.yaml"
    if not active_path.exists() or force:
        active_policy = default_safe_policy()
        active_policy.metadata.update({
            "name": "active",
            "description": "Active policy - currently enforced rules (required)",
            "created_at": datetime.now().isoformat(),
            "note": "This is the only required policy file. It represents the normal production state.",
        })
        save_policy(active_policy, active_path)
    
    # 2. Create shadow.yaml (derived from active, enforcement=SHADOW)
    shadow_path = policy_dir / "shadow.yaml"
    if not shadow_path.exists() or force:
        # Load active policy first (must exist)
        if active_path.exists():
            active_policy = load_policy(active_path)
        else:
            active_policy = default_safe_policy()
        
        # Derive shadow: same structure, all enforcement = SHADOW
        shadow_policy = active_policy.model_copy(deep=True)
        for validator_id, config in shadow_policy.validators.items():
            config.enforcement = EnforcementMode.SHADOW
        
        shadow_policy.metadata.update({
            "name": "shadow",
            "description": "Shadow mode policy - observe without blocking",
            "created_at": datetime.now().isoformat(),
            "derived_from": "active.yaml",
            "note": "This is derived from active.yaml with all enforcement modes set to SHADOW. "
                    "It does not introduce new rules, only changes execution intensity.",
        })
        save_policy(shadow_policy, shadow_path)
    
    # 3. Create breakglass.yaml (empty template, disabled)
    breakglass_path = policy_dir / "breakglass.yaml"
    if not breakglass_path.exists() or force:
        breakglass_policy = Policy(
            version="v1",
            validators={},  # Empty - breakglass cannot add validators
            global_override=OverrideConfig(
                enabled=False,  # Disabled by default
                require_token=True,
                token_env_var="FAILCORE_OVERRIDE_TOKEN",
                audit_required=True,
            ),
            metadata={
                "name": "breakglass",
                "description": "Emergency override policy - use with extreme caution",
                "created_at": datetime.now().isoformat(),
                "warning": (
                    "This file should remain empty by default. "
                    "Only add exceptions when emergency override is needed. "
                    "Breakglass can only: add exceptions (with expires_at), enable override, "
                    "or downgrade enforcement. It cannot add new validators or change config."
                ),
            },
        )
        save_policy(breakglass_policy, breakglass_path)


def ensure_policy_files(project_root: Optional[Path] = None) -> bool:
    """
    Ensure policy files exist (idempotent initialization).
    
    This is the single entry point for policy file initialization.
    Called automatically when ValidationEngine first runs and detects missing files.
    
    Args:
        project_root: Project root directory
    
    Returns:
        True if files were created, False if they already existed
    
    Example:
        >>> # Called automatically by engine, or manually:
        >>> ensure_policy_files()
        True  # Files created
        >>> ensure_policy_files()
        False  # Files already exist
    """
    policy_dir = get_policy_dir(project_root)
    active_path = policy_dir / "active.yaml"
    
    # Check if initialization is needed
    if active_path.exists():
        return False
    
    # Initialize (idempotent)
    init_policy_files(project_root, force=False)
    return True


__all__ = [
    # Core layer (I/O-free, for extraction)
    "parse_policy_from_str",
    "parse_policy_from_dict",
    "serialize_policy_to_str",
    "serialize_policy_to_dict",
    # API layer (with I/O)
    "load_policy",
    "dump_policy",
    "save_policy",
    "get_policy_dir",
    "ensure_policy_dir",
    # Merge
    "merge_policies",
    "load_merged_policy",
    # Initialization (idempotent)
    "init_policy_files",
    "ensure_policy_files",
]
