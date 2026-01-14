# failcore/core/validate/builtin/security.py
r"""
Security-focused validators for path traversal, sandbox enforcement, etc.

This module provides validators for production security requirements:
- Path traversal detection (../ attacks)
- Sandbox boundary enforcement
- Symlink/junction resolution checks
- Windows-specific path family detection (\\?\, \\.\, ADS, etc.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import os
import sys

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, DecisionOutcome, RiskLevel
from failcore.core.validate.constants import MetaKeys
from failcore.utils.paths import format_relative_path


class PathTraversalValidator(BaseValidator):
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
    """
    
    @property
    def id(self) -> str:
        return "security_path_traversal"
    
    @property
    def domain(self) -> str:
        return "security"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for validator configuration"""
        return {
            "type": "object",
            "properties": {
                "path_params": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Parameter names to check (path, file_path, etc.)",
                },
                "sandbox_root": {
                    "type": "string",
                    "description": "Sandbox root directory (optional, can be from context)",
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            "path_params": ["path", "file_path", "relative_path"],
            "sandbox_root": None,
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate path traversal validation
        
        Args:
            context: Validation context (tool, params, etc.)
            config: Validator configuration (path_params, sandbox_root)
            
        Returns:
            List of Decision objects (empty if validation passes)
        """
        decisions: List[Decision] = []
        
        # Get configuration
        cfg = self._get_config(config)
        path_params = cfg.get("path_params", ["path", "file_path", "relative_path"])
        config_sandbox_root = cfg.get("sandbox_root")
        
        # Get sandbox root from context metadata (priority: context > config > cwd)
        sandbox_root = self._get_sandbox_root(context, config_sandbox_root)
        sandbox_root_source = self._get_sandbox_root_source(context, config_sandbox_root)
        
        # Find first existing path parameter
        path_value = None
        found_param = None
        for pname in path_params:
            if pname in context.params:
                path_value = context.params[pname]
                found_param = pname
                break
        
        if not path_value:
            # No path parameter found, skip check
            return []
        
        # Convert to string for pattern checking
        path_str = str(path_value)
        
        # === Trailing dots/spaces check (BEFORE any normalization) ===
        path_str_clean = path_str.rstrip(". ")
        if path_str_clean != path_str:
            return [
                Decision.block(
                    code="FC_SEC_PATH_TRAILING_MANIPULATION",
                    validator_id=self.id,
                    message=f"Path with trailing dots/spaces not allowed: '{path_value}'",
                    evidence={
                        "path": str(path_value),
                        "normalized": path_str_clean,
                        "reason": "trailing_manipulation",
                        "field": found_param,
                        "suggestion": "Remove trailing dots and spaces",
                        "sandbox_root": str(sandbox_root),
                        "sandbox_root_source": sandbox_root_source,
                    },
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        # Now safe to work with cleaned string
        path_str = path_str.strip()
        
        # === Windows-specific path family checks ===
        if sys.platform == 'win32':
            # Block NT path prefixes (\\?\, \\.\)
            if path_str.startswith(("\\\\?\\", "\\\\.\\")):
                return [
                    Decision.block(
                        code="FC_SEC_PATH_NT_PREFIX",
                        validator_id=self.id,
                        message=f"NT path prefix not allowed: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "sandbox_root": str(sandbox_root),
                            "sandbox_root_source": sandbox_root_source,
                            "reason": "nt_path_prefix",
                            "field": found_param,
                            "suggestion": "Use regular relative paths",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
            
            # Block device paths (GLOBALROOT, Device\\)
            upper_path = path_str.upper()
            if "GLOBALROOT" in upper_path or "DEVICE\\" in upper_path:
                return [
                    Decision.block(
                        code="FC_SEC_PATH_DEVICE",
                        validator_id=self.id,
                        message=f"Device path not allowed: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "sandbox_root": str(sandbox_root),
                            "sandbox_root_source": sandbox_root_source,
                            "reason": "device_path",
                            "field": found_param,
                            "suggestion": "Use regular file paths",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
            
            # Check for Alternate Data Stream (ADS)
            colon_count = path_str.count(":")
            if colon_count > 1 or (colon_count == 1 and not (len(path_str) >= 2 and path_str[1] == ":")):
                return [
                    Decision.block(
                        code="FC_SEC_PATH_ADS",
                        validator_id=self.id,
                        message=f"Alternate Data Stream not allowed: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "sandbox_root": str(sandbox_root),
                            "sandbox_root_source": sandbox_root_source,
                            "reason": "alternate_data_stream",
                            "field": found_param,
                            "suggestion": "Remove ':' from filename",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
        
        # === Normalize and sanitize input ===
        try:
            # Normalize path separators (detect mixed separators)
            if "\\" in path_str and "/" in path_str:
                return [
                    Decision.block(
                        code="FC_SEC_PATH_MIXED_SEPARATORS",
                        validator_id=self.id,
                        message=f"Mixed path separators not allowed: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "reason": "mixed_separators",
                            "field": found_param,
                            "suggestion": "Use consistent separators (/ or \\)",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
            
            target_path = Path(path_value)
            
            # Block UNC paths (Windows) immediately
            if str(path_value).startswith(("\\\\", "//")):
                return [
                    Decision.block(
                        code="FC_SEC_PATH_UNC",
                        validator_id=self.id,
                        message=f"UNC paths are not allowed: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "sandbox_root": str(sandbox_root),
                            "sandbox_root_source": sandbox_root_source,
                            "reason": "unc_path",
                            "field": found_param,
                            "suggestion": f"Use paths within sandbox",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
            
            # Handle absolute vs relative paths
            if target_path.is_absolute():
                full_path = target_path
            else:
                full_path = sandbox_root / target_path
            
            # === Resolve symlinks/junctions ===
            resolved_path = self._resolve_path(full_path, sandbox_root, path_value, found_param, sandbox_root_source, context)
            
            # Check if resolved path is a Decision (error case)
            if isinstance(resolved_path, Decision):
                return [resolved_path]
            
            # === Final boundary check ===
            try:
                resolved_path.relative_to(sandbox_root)
                # Path is within sandbox, validation passes
                return []
            except ValueError:
                # Path is outside sandbox
                is_traversal_attempt = ".." in str(path_value)
                code = "FC_SEC_PATH_TRAVERSAL" if is_traversal_attempt else "FC_SEC_SANDBOX_VIOLATION"
                return [
                    Decision.block(
                        code=code,
                        validator_id=self.id,
                        message=f"Path traversal detected: '{path_value}' attempts to escape sandbox" if is_traversal_attempt else f"Path is outside sandbox boundary: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "sandbox_root": str(sandbox_root),
                            "sandbox_root_source": sandbox_root_source,
                            "resolved": str(resolved_path),
                            "reason": "traversal" if is_traversal_attempt else "outside_sandbox",
                            "field": found_param,
                            "suggestion": "Remove '../' path components" if is_traversal_attempt else "Path must be within sandbox",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
            
        except Exception as e:
            # Path resolution failed
            return [
                Decision.block(
                    code="FC_SEC_PATH_INVALID",
                    validator_id=self.id,
                    message=f"Invalid path: {e}",
                    evidence={
                        "path": str(path_value),
                        "error": str(e),
                        "field": found_param,
                        "suggestion": "Provide a valid file path",
                    },
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default
    
    def _get_sandbox_root(self, context: Context, config_sandbox_root: Optional[str]) -> Path:
        """Get sandbox root from context metadata or config"""
        # Priority: Context metadata > Config > cwd
        if hasattr(context, 'metadata') and context.metadata:
            sandbox_root = context.metadata.get(MetaKeys.SANDBOX_ROOT)
            if sandbox_root:
                return Path(sandbox_root).resolve()
            # Fallback to legacy keys
            sandbox_root = context.metadata.get("sandbox_root") or context.metadata.get("sandbox")
            if sandbox_root:
                return Path(sandbox_root).resolve()
        
        if hasattr(context, 'state') and context.state:
            sandbox_root = context.state.get("sandbox_root") or context.state.get("sandbox")
            if sandbox_root:
                return Path(sandbox_root).resolve()
        
        if config_sandbox_root:
            return Path(config_sandbox_root).resolve()
        
        return Path(os.getcwd()).resolve()
    
    def _get_sandbox_root_source(self, context: Context, config_sandbox_root: Optional[str]) -> str:
        """Get sandbox root source for evidence"""
        if hasattr(context, 'metadata') and context.metadata:
            if MetaKeys.SANDBOX_ROOT in context.metadata:
                return "context:metadata.failcore.sys.sandbox_root"
            if "sandbox_root" in context.metadata:
                return "context:metadata.sandbox_root"
            if "sandbox" in context.metadata:
                return "context:metadata.sandbox"
        
        if hasattr(context, 'state') and context.state:
            if "sandbox_root" in context.state:
                return "context:state.sandbox_root"
            if "sandbox" in context.state:
                return "context:state.sandbox"
        
        if config_sandbox_root:
            return "config"
        
        return "cwd_fallback"
    
    def _resolve_path(
        self,
        full_path: Path,
        sandbox_root: Path,
        path_value: Any,
        found_param: str,
        sandbox_root_source: str,
        context: Context,
    ) -> Optional[Union[Path, Decision]]:
        """Resolve path, handling symlinks/junctions"""
        if full_path.exists():
            resolved_path = full_path.resolve()
            
            # Verify all parent directories are within sandbox
            current = resolved_path
            while current != current.parent:
                current = current.parent
                if current == sandbox_root:
                    break
                try:
                    current.relative_to(sandbox_root)
                except ValueError:
                    # Parent is outside sandbox
                    is_traversal = ".." in str(path_value)
                    return Decision.block(
                        code="FC_SEC_SANDBOX_VIOLATION",
                        validator_id=self.id,
                        message=f"Path escapes sandbox via symlink/junction: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "sandbox_root": str(sandbox_root),
                            "sandbox_root_source": sandbox_root_source,
                            "resolved": str(resolved_path),
                            "escape_point": str(current),
                            "reason": "symlink_escape",
                            "field": found_param,
                            "suggestion": "Remove symlinks/junctions pointing outside sandbox",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
            return resolved_path
        else:
            # Path doesn't exist - check parent directory
            parent = full_path.parent
            if parent.exists():
                resolved_parent = parent.resolve()
                try:
                    resolved_parent.relative_to(sandbox_root)
                except ValueError:
                    is_traversal = ".." in str(path_value)
                    return Decision.block(
                        code="FC_SEC_PATH_TRAVERSAL" if is_traversal else "FC_SEC_SANDBOX_VIOLATION",
                        validator_id=self.id,
                        message=f"Path traversal detected: '{path_value}' attempts to escape sandbox using '../'" if is_traversal else f"Parent directory is outside sandbox: '{path_value}'",
                        evidence={
                            "path": str(path_value),
                            "sandbox": format_relative_path(sandbox_root),
                            "sandbox_root": str(sandbox_root),
                            "sandbox_root_source": sandbox_root_source,
                            "parent": str(resolved_parent),
                            "reason": "parent_outside_sandbox",
                            "field": found_param,
                            "suggestion": "Remove '../' path components" if is_traversal else "Path must be within sandbox",
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                return resolved_parent / full_path.name
            else:
                # Parent doesn't exist - find first existing ancestor
                ancestor = parent
                while not ancestor.exists() and ancestor != ancestor.parent:
                    ancestor = ancestor.parent
                
                if ancestor.exists():
                    resolved_ancestor = ancestor.resolve()
                    try:
                        resolved_ancestor.relative_to(sandbox_root)
                    except ValueError:
                        is_traversal = ".." in str(path_value)
                        return Decision.block(
                            code="FC_SEC_PATH_TRAVERSAL" if is_traversal else "FC_SEC_SANDBOX_VIOLATION",
                            validator_id=self.id,
                            message=f"Path traversal detected: '{path_value}' attempts to escape sandbox using '../'" if is_traversal else f"Path would be created outside sandbox: '{path_value}'",
                            evidence={
                                "path": str(path_value),
                                "sandbox": format_relative_path(sandbox_root),
                                "sandbox_root": str(sandbox_root),
                                "sandbox_root_source": sandbox_root_source,
                                "ancestor": str(resolved_ancestor),
                                "reason": "ancestor_outside_sandbox",
                                "field": found_param,
                                "suggestion": "Remove '../' path components" if is_traversal else "Path must be within sandbox",
                            },
                            tool=context.tool,
                            step_id=context.step_id,
                        )
                    return resolved_ancestor / full_path.relative_to(ancestor)
                else:
                    return full_path.resolve()


__all__ = [
    "PathTraversalValidator",
]
