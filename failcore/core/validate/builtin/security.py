# failcore/core/validate/builtin/security.py
r"""
Security-focused builtin for path traversal, sandbox enforcement, etc.

This module provides builtin for production security requirements:
- Path traversal detection (../ attacks)
- Sandbox boundary enforcement
- Symlink/junction resolution checks
- Windows-specific path family detection (\\?\, \\.\, ADS, etc.)
"""

from pathlib import Path
import os
import sys
from typing import Any, Dict
from .contract import PreconditionValidator, ValidationResult
from failcore.utils.paths import format_relative_path


def path_traversal_precondition(
    *param_names: str,
    sandbox_root: str = None
) -> PreconditionValidator:
    """
    Path traversal defense validator with comprehensive attack detection.
    
    Protects against:
    - Path traversal (../)
    - Absolute paths (C:\\, /, \\)
    - UNC paths (\\\\server\\share)
    - Windows special paths (\\\\?\\, \\\\.\\, GLOBALROOT, Device)
    - Alternate Data Streams (file.txt:stream)
    - Symlink/junction escapes (resolves to real path)
    - Mixed separators and trailing dots/spaces
    
    Args:
        *param_names: Parameter names to check (path, file_path, etc.)
        sandbox_root: Sandbox root directory (uses cwd if None)
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> from failcore.core.validate.builtin.security import path_traversal_precondition
        >>> registry.register_precondition(
        ...     "write_file",
        ...     path_traversal_precondition("path", sandbox_root="/app/workspace")
        ... )
    """
    if not param_names:
        param_names = ("path",)
    
    # Determine sandbox root directory
    if sandbox_root is None:
        sandbox_root = os.getcwd()
    
    sandbox_root = Path(sandbox_root).resolve()
    
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        # Find first existing parameter
        path_value = None
        found_param = None
        for pname in param_names:
            if pname in params:
                path_value = params[pname]
                found_param = pname
                break
        
        if not path_value:
            # No path parameter found, skip check
            return ValidationResult.success(
                message="No path parameter found",
                code="PATH_CHECK_SKIPPED"
            )
        
        # Convert to string for pattern checking (DO NOT strip - we need to detect trailing manipulation)
        path_str = str(path_value)
        
        # === Trailing dots/spaces check (BEFORE any normalization) ===
        # Windows auto-strips these, so they're potential evasion vectors
        path_str_clean = path_str.rstrip(". ")
        if path_str_clean != path_str:
            # Path changed after normalization - potential evasion
            return ValidationResult.failure(
                message=f"Path with trailing dots/spaces not allowed: '{path_value}'",
                code="PATH_INVALID",
                details={
                    "path": str(path_value),
                    "normalized": path_str_clean,
                    "reason": "trailing_manipulation",
                    "field": found_param,
                    "suggestion": "Remove trailing dots and spaces"
                }
            )
        
        # Now safe to work with cleaned string
        path_str = path_str.strip()
        
        # === Windows-specific path family checks ===
        if sys.platform == 'win32':
            # Block NT path prefixes (\\?\, \\.\)
            if path_str.startswith(("\\\\?\\", "\\\\.\\")):
                return ValidationResult.failure(
                    message=f"NT path prefix not allowed: '{path_value}'",
                    code="SANDBOX_VIOLATION",
                    details={
                        "path": str(path_value),
                        "sandbox": format_relative_path(sandbox_root),
                        "reason": "nt_path_prefix",
                        "field": found_param,
                        "suggestion": "Use regular relative paths"
                    }
                )
            
            # Block device paths (GLOBALROOT, Device\)
            upper_path = path_str.upper()
            if "GLOBALROOT" in upper_path or "DEVICE\\" in upper_path:
                return ValidationResult.failure(
                    message=f"Device path not allowed: '{path_value}'",
                    code="SANDBOX_VIOLATION",
                    details={
                        "path": str(path_value),
                        "sandbox": format_relative_path(sandbox_root),
                        "reason": "device_path",
                        "field": found_param,
                        "suggestion": "Use regular file paths"
                    }
                )
            
            # Check for Alternate Data Stream (ADS)
            # Allow drive letter colon (C:), but block ADS (file.txt:stream)
            colon_count = path_str.count(":")
            if colon_count > 1 or (colon_count == 1 and not (len(path_str) >= 2 and path_str[1] == ":")):
                return ValidationResult.failure(
                    message=f"Alternate Data Stream not allowed: '{path_value}'",
                    code="SANDBOX_VIOLATION",
                    details={
                        "path": str(path_value),
                        "sandbox": format_relative_path(sandbox_root),
                        "reason": "alternate_data_stream",
                        "field": found_param,
                        "suggestion": "Remove ':' from filename"
                    }
                )
        
        # === Normalize and sanitize input ===
        try:
            # Normalize path separators (detect mixed separators)
            if "\\" in path_str and "/" in path_str:
                return ValidationResult.failure(
                    message=f"Mixed path separators not allowed: '{path_value}'",
                    code="PATH_INVALID",
                    details={
                        "path": str(path_value),
                        "reason": "mixed_separators",
                        "field": found_param,
                        "suggestion": "Use consistent separators (/ or \\)"
                    }
                )
            
            target_path = Path(path_value)
            
            # Block UNC paths (Windows) immediately
            if str(path_value).startswith(("\\\\", "//")):
                return ValidationResult.failure(
                    message=f"UNC paths are not allowed: '{path_value}'",
                    code="SANDBOX_VIOLATION",
                    details={
                        "path": str(path_value),
                        "sandbox": format_relative_path(sandbox_root),
                        "reason": "unc_path",
                        "field": found_param,
                        "suggestion": f"Use paths within sandbox"
                    }
                )
            
            # Handle absolute vs relative paths
            if target_path.is_absolute():
                # Absolute path: use as-is (will check if within sandbox later)
                full_path = target_path
            else:
                # Relative path: construct relative to sandbox
                full_path = sandbox_root / target_path
            
            # === Critical: Resolve symlinks/junctions at EVERY level ===
            # For existing paths: resolve and check (handles symlinks/junctions)
            # For non-existing paths: check parent directory
            if full_path.exists():
                # Path exists - resolve it (this handles symlinks/junctions)
                resolved_path = full_path.resolve()
                
                # CRITICAL: Also verify that ALL parent directories are within sandbox
                # This prevents intermediate junction attacks
                try:
                    # Check if any parent is outside sandbox before reaching the file
                    current = resolved_path
                    while current != current.parent:
                        current = current.parent
                        if current == sandbox_root:
                            break
                        # Verify parent is within sandbox
                        try:
                            current.relative_to(sandbox_root)
                        except ValueError:
                            return ValidationResult.failure(
                                message=f"Path escapes sandbox via symlink/junction: '{path_value}'",
                                code="SANDBOX_VIOLATION",
                                details={
                                    "path": str(path_value),
                                    "sandbox": format_relative_path(sandbox_root),
                                    "resolved": str(resolved_path),
                                    "escape_point": str(current),
                                    "reason": "symlink_escape",
                                    "field": found_param,
                                    "suggestion": "Remove symlinks/junctions pointing outside sandbox"
                                }
                            )
                except Exception:
                    pass  # Continue to main boundary check
                
            else:
                # Path doesn't exist yet (common for write operations)
                # Check parent directory to prevent creating outside sandbox
                parent = full_path.parent
                if parent.exists():
                    resolved_parent = parent.resolve()
                    
                    # Verify parent is within sandbox
                    try:
                        resolved_parent.relative_to(sandbox_root)
                    except ValueError:
                        # Check if this is path traversal
                        is_traversal = ".." in str(path_value)
                        if is_traversal:
                            return ValidationResult.failure(
                                message=f"Path traversal detected: '{path_value}' attempts to escape sandbox using '../'",
                                code="PATH_TRAVERSAL",
                                details={
                                    "path": str(path_value),
                                    "sandbox": format_relative_path(sandbox_root),
                                    "parent": str(resolved_parent),
                                    "reason": "parent_outside_sandbox",
                                    "field": found_param,
                                    "suggestion": "Remove '../' path components"
                                }
                            )
                        else:
                            return ValidationResult.failure(
                                message=f"Parent directory is outside sandbox: '{path_value}'",
                                code="SANDBOX_VIOLATION",
                                details={
                                    "path": str(path_value),
                                    "sandbox": format_relative_path(sandbox_root),
                                    "parent": str(resolved_parent),
                                    "reason": "parent_outside_sandbox",
                                    "field": found_param,
                                    "suggestion": "Path must be within sandbox"
                                }
                            )
                    
                    # Reconstruct resolved path using resolved parent + filename
                    resolved_path = resolved_parent / full_path.name
                else:
                    # Parent doesn't exist either - find first existing ancestor
                    ancestor = parent
                    while not ancestor.exists() and ancestor != ancestor.parent:
                        ancestor = ancestor.parent
                    
                    if ancestor.exists():
                        resolved_ancestor = ancestor.resolve()
                        # Ensure ancestor is within sandbox
                        try:
                            resolved_ancestor.relative_to(sandbox_root)
                        except ValueError:
                            # Check if this is path traversal
                            is_traversal = ".." in str(path_value)
                            if is_traversal:
                                return ValidationResult.failure(
                                    message=f"Path traversal detected: '{path_value}' attempts to escape sandbox using '../'",
                                    code="PATH_TRAVERSAL",
                                    details={
                                        "path": str(path_value),
                                        "sandbox": format_relative_path(sandbox_root),
                                        "ancestor": str(resolved_ancestor),
                                        "reason": "ancestor_outside_sandbox",
                                        "field": found_param,
                                        "suggestion": "Remove '../' path components"
                                    }
                                )
                            else:
                                return ValidationResult.failure(
                                    message=f"Path would be created outside sandbox: '{path_value}'",
                                    code="SANDBOX_VIOLATION",
                                    details={
                                        "path": str(path_value),
                                        "sandbox": format_relative_path(sandbox_root),
                                        "ancestor": str(resolved_ancestor),
                                        "reason": "ancestor_outside_sandbox",
                                        "field": found_param,
                                        "suggestion": "Path must be within sandbox"
                                    }
                                )
                        # Reconstruct full resolved path
                        resolved_path = resolved_ancestor / full_path.relative_to(ancestor)
                    else:
                        # No existing ancestor found (shouldn't happen in practice)
                        resolved_path = full_path.resolve()
            
            # === Final boundary check: is resolved path within sandbox? ===
            try:
                resolved_path.relative_to(sandbox_root)
            except ValueError:
                # Path is outside sandbox
                # Distinguish between traversal (..) and other violations
                is_traversal_attempt = ".." in str(path_value)
                
                if is_traversal_attempt:
                    return ValidationResult.failure(
                        message=f"Path traversal detected: '{path_value}' attempts to escape sandbox using '../'",
                        code="PATH_TRAVERSAL",
                        details={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "resolved": str(resolved_path),
                            "reason": "traversal",
                            "field": found_param,
                            "suggestion": "Remove '../' path components"
                        }
                    )
                else:
                    return ValidationResult.failure(
                        message=f"Path is outside sandbox boundary: '{path_value}'",
                        code="SANDBOX_VIOLATION",
                        details={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "resolved": str(resolved_path),
                            "reason": "outside_sandbox",
                            "field": found_param,
                            "suggestion": "Path must be within sandbox"
                        }
                    )
            
            # Path is within sandbox, pass check
            return ValidationResult.success(
                message=f"Path '{path_value}' is within sandbox",
                code="PATH_SAFE"
            )
            
        except Exception as e:
            # Path resolution failed (e.g., invalid path format)
            return ValidationResult.failure(
                message=f"Invalid path: {e}",
                code="PATH_INVALID",
                details={
                    "path": str(path_value),
                    "error": str(e),
                    "field": found_param,
                    "suggestion": "Provide a valid file path"
                }
            )
    
    return PreconditionValidator(
        name=f"path_traversal_check({'|'.join(param_names)})",
        condition=check,
        message="Path traversal detected",
        code="PATH_TRAVERSAL"
    )


__all__ = [
    "path_traversal_precondition",
]

