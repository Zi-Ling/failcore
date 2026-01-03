# failcore/utils/path_resolver.py
"""
Path resolution and security validation.

Separates path resolution logic from RunContext for better testability
and maintainability.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Literal


PathType = Literal['name', 'relative', 'absolute']


class PathResolver:
    """
    Resolves and validates paths with security constraints.
    
    Responsible for:
    - Path classification (name/relative/absolute)
    - Path resolution and normalization
    - Security boundary enforcement (project root)
    - Whitelist validation for external paths
    """
    
    def __init__(
        self,
        project_root: Path,
        allow_outside_root: bool = False,
    ):
        """
        Initialize path resolver.
        
        Args:
            project_root: Project root directory (security boundary)
            allow_outside_root: Allow paths outside project root (requires whitelist)
        """
        self.project_root = project_root.resolve()
        self.allow_outside_root = allow_outside_root
    
    def classify_path(self, path_str: str) -> PathType:
        """
        Classify path type: 'name', 'relative', or 'absolute'.
        
        Args:
            path_str: Path string to classify
        
        Returns:
            'name': Name-only (no separators)
            'relative': Relative path (has separators but not absolute)
            'absolute': Absolute path
        """
        if not path_str:
            return 'name'
        
        p = Path(path_str)
        
        # Check if absolute
        if p.is_absolute():
            return 'absolute'
        
        # Check if contains path separators
        if '/' in path_str or '\\' in path_str:
            return 'relative'
        
        # Just a name
        return 'name'
    
    def resolve(
        self,
        path_str: str,
        default_location: Path,
        path_category: str,  # 'trace' or 'sandbox'
        allowed_roots: Optional[list] = None,
    ) -> Path:
        """
        Resolve path with security constraints and whitelist support.
        
        Philosophy:
        - Path format (absolute/relative) is just syntax, not security
        - Security boundary is project root by default
        - External paths require explicit whitelist
        
        Args:
            path_str: Original path string
            default_location: Default location for name-only paths
            path_category: 'trace' or 'sandbox' for error messages
            allowed_roots: Whitelist of allowed root directories (outside project)
        
        Returns:
            Resolved absolute path
        
        Raises:
            ValueError: If path escapes project root and not in whitelist
        """
        path_type = self.classify_path(path_str)
        
        if path_type == 'name':
            # Name-only: put in default location
            return default_location / path_str
        
        elif path_type == 'relative':
            # Relative path: resolve against project root
            resolved = (self.project_root / path_str).resolve()
            
            # Security check: must stay within project root
            if not self._is_within_project(resolved):
                raise ValueError(
                    f"Security violation: {path_category} path '{path_str}' "
                    f"escapes project root. Resolved to: {resolved}"
                )
            
            return resolved
        
        elif path_type == 'absolute':
            # Absolute path: resolve directly
            resolved = Path(path_str).resolve()
            
            # Check if within project root
            if self._is_within_project(resolved):
                # Within project root - always allowed
                return resolved
            
            # Outside project root - check permissions and whitelist
            return self._validate_external_path(
                resolved,
                path_str,
                path_category,
                allowed_roots
            )
        
        else:
            raise ValueError(f"Unknown path type: {path_type}")
    
    def _is_within_project(self, resolved: Path) -> bool:
        """Check if resolved path is within project root."""
        try:
            resolved.relative_to(self.project_root)
            return True
        except ValueError:
            return False
    
    def _validate_external_path(
        self,
        resolved: Path,
        original: str,
        path_category: str,
        allowed_roots: Optional[list],
    ) -> Path:
        """
        Validate external path against whitelist.
        
        Args:
            resolved: Resolved absolute path
            original: Original path string
            path_category: 'trace' or 'sandbox'
            allowed_roots: Whitelist of allowed root directories
        
        Returns:
            Resolved path if valid
        
        Raises:
            ValueError: If path not allowed
        """
        # Path is outside project root
        if not self.allow_outside_root:
            raise ValueError(
                f"Security violation: {path_category} path escapes project root.\n"
                f"  Input: {original}\n"
                f"  Resolved to: {resolved}\n"
                f"  Project root: {self.project_root}\n"
                f"  → Set allow_outside_root=True and provide whitelist to allow external paths.\n"
                f"  Example: allow_outside_root=True, allowed_{path_category}_roots=[Path('/tmp')]"
            )
        
        # Check whitelist
        if not allowed_roots:
            raise ValueError(
                f"Security violation: {path_category} path outside project root without whitelist.\n"
                f"  Input: {original}\n"
                f"  Resolved to: {resolved}\n"
                f"  → Provide allowed_{path_category}_roots=[...] to whitelist external paths."
            )
        
        # Verify path is within one of the allowed roots
        for allowed_root in allowed_roots:
            allowed_root_resolved = Path(allowed_root).resolve()
            try:
                resolved.relative_to(allowed_root_resolved)
                # Path is within this allowed root - OK
                return resolved
            except ValueError:
                continue
        
        # Not in any allowed root
        allowed_roots_str = ", ".join(str(r) for r in allowed_roots)
        raise ValueError(
            f"Security violation: {path_category} path not in whitelist.\n"
            f"  Input: {original}\n"
            f"  Resolved to: {resolved}\n"
            f"  Allowed roots: {allowed_roots_str}\n"
            f"  → Path must be within one of the whitelisted directories."
        )


__all__ = ['PathResolver', 'PathType']
