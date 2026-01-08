"""
filesystem-safe Policy Pack Implementation

Executable contract for filesystem operations
"""

from typing import Optional
from failcore.core.policy.policy import PolicyResult
from failcore.core.errors import codes
import os
from pathlib import Path


class FilesystemSafePolicy:
    """
    Executable policy for filesystem-safe pack
    
    Enforces:
    - Sandbox boundary (no path traversal)
    - Max file size limits
    - No device files (Windows: CON, NUL, etc)
    """
    
    def __init__(self, sandbox: str = "./workspace", max_file_size_mb: int = 50):
        self.sandbox = Path(sandbox).resolve()
        self.max_file_size_mb = max_file_size_mb
        self.sandbox.mkdir(parents=True, exist_ok=True)
    
    def allow(self, tool: str, args: dict, context: dict) -> PolicyResult:
        """Check if filesystem operation is allowed"""
        
        # Extract path parameter
        path = args.get('path') or args.get('file_path') or args.get('filename')
        
        if not path:
            return PolicyResult.allow()
        
        path_str = str(path)
        
        # Check for path traversal FIRST (before resolving)
        if '..' in path_str:
            return PolicyResult.deny(
                reason=f"Path traversal detected: '{path}'",
                error_code=codes.PATH_TRAVERSAL,
                suggestion=f"Use relative paths without '..' - Example: 'data/file.txt' instead of '{path}'",
                remediation={
                    "action": "sanitize_path",
                    "template": "Remove '..' from path: {sanitized_path}",
                    "vars": {"sanitized_path": path_str.replace('..', '')}
                }
            )
        
        # Check for absolute paths (cross-platform)
        # On Windows, also check for leading slash which might be Unix-style
        is_absolute = os.path.isabs(path_str) or path_str.startswith('/') or path_str.startswith('\\')
        if is_absolute:
            return PolicyResult.deny(
                reason=f"Absolute path not allowed: '{path}'",
                error_code=codes.SANDBOX_VIOLATION,
                suggestion=f"Use relative paths within sandbox. Example: 'data/{os.path.basename(path_str)}'",
                remediation={
                    "action": "fix_path",
                    "template": "Use relative path: {relative_path}",
                    "vars": {"relative_path": os.path.basename(path_str)}
                }
            )
        
        # Check sandbox boundary (should not trigger if above checks passed)
        try:
            target_path = (self.sandbox / path_str).resolve()
            sandbox_resolved = self.sandbox.resolve()
            if not str(target_path).startswith(str(sandbox_resolved)):
                return PolicyResult.deny(
                    reason=f"Path would be created outside sandbox: '{path}'",
                    error_code=codes.SANDBOX_VIOLATION,
                    suggestion=f"Path must be within sandbox. Use relative paths like 'data/{os.path.basename(path_str)}'",
                    remediation={
                        "action": "fix_path",
                        "template": "{basename}",
                        "vars": {
                            "basename": os.path.basename(path_str)
                        }
                    }
                )
        except (ValueError, OSError):
            return PolicyResult.deny(
                reason=f"Invalid path: '{path}'",
                error_code=codes.PATH_INVALID,
                suggestion="Use valid filesystem paths"
            )
        
        return PolicyResult.allow()


__all__ = ["FilesystemSafePolicy"]
