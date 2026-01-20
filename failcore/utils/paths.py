# failcore/utils/paths.py
"""
Shared path utilities for FailCore.

Design goals:
- Deterministic and explicit: creating a run is a deliberate action.
- No hidden side-effects in "get_*" helpers (they don't create directories).
- Unified naming: run_<HHMMSS> or proxy_<HHMMSS>
- Prefer pathlib.Path throughout; convert to str only at CLI edges if needed.
- Smart project root detection: avoids path pollution across different directories
- Never resolve relative to FailCore's package location
- If no project markers are found, fallback to ~/.failcore/ (NOT CWD)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
import hashlib
import os
import sys
import logging

from failcore.core.types.step import generate_run_id

logger = logging.getLogger(__name__)


# Markers that indicate a project root directory
# NOTE:
# - DO NOT include ".failcore" here; once created it would hijack future detection.
# - Use ".failcore_root" as the explicit anchor (file or dir).
PROJECT_ROOT_MARKERS = [
    ".failcore_root",     # explicit anchor (recommended)
    ".git",               # Git repository (strong signal)
    "pyproject.toml",     # Python project (PEP 518)
    "setup.py",           # Python project (legacy)
    "setup.cfg",          # Python project (legacy)
]

# Global cache for project root (resolved once per process)
_PROJECT_ROOT_CACHE: Optional[Path] = None

# Optional: enable debug prints (kept minimal; does not create files)
_DEBUG = os.getenv("FAILCORE_DEBUG_PATHS", "").strip().lower() in {"1", "true", "yes"}


def _debug(msg: str) -> None:
    if _DEBUG:
        print(f"[failcore.paths] {msg}", file=sys.stderr)


def _is_relative_to(path: Path, base: Path) -> bool:
    """Python<3.9 compatibility for Path.is_relative_to()."""
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _entry_script_dir() -> Optional[Path]:
    """
    Best-effort entry script directory detection.
    - For 'python script.py': sys.argv[0] points to script
    - For '-m package' / REPL / notebooks: may be unusable
    """
    if not getattr(sys, "argv", None):
        return None
    if not sys.argv:
        return None

    raw = sys.argv[0]
    if not raw:
        return None

    try:
        p = Path(raw)
        # If it's relative, resolve against CWD (user context), not package dir.
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        else:
            p = p.resolve()

        if p.exists():
            return p.parent if p.is_file() else p
    except Exception:
        return None

    return None


def _find_root_from_path(start_path: Path) -> Optional[Path]:
    """
    Traverse upward from start_path looking for project markers.
    Returns the directory that contains any marker.
    """
    try:
        current = start_path.resolve()
    except Exception:
        current = start_path

    # Ensure we're scanning a directory
    if current.is_file():
        current = current.parent

    while True:
        for marker in PROJECT_ROOT_MARKERS:
            if (current / marker).exists():
                _debug(f"root marker hit: {(current / marker)}")
                return current

        # Reached filesystem root: still need to check that root (done above),
        # then terminate.
        if current.parent == current:
            return None

        current = current.parent


def _home_fallback_root(seed: str) -> Path:
    """
    Fallback root under ~/.failcore/projects/<hash>.
    Prevents mixing multiple marker-less 'projects' into the same runs folder.
    """
    h = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return Path.home() / ".failcore" / "projects" / h


def find_project_root() -> Path:
    """
    Find project root directory using intelligent detection.

    Strategy:
    0. If FAILCORE_PROJECT_ROOT is set, use it (explicit override).
    1. From CWD, traverse upward looking for project markers
    2. From entry script directory, traverse upward looking for markers
    3. Fallback to ~/.failcore/projects/<hash> (NOT CWD)

    Returns:
        Path to project root directory (NOT including ".failcore")
    """
    global _PROJECT_ROOT_CACHE

    if _PROJECT_ROOT_CACHE is not None:
        return _PROJECT_ROOT_CACHE

    # 0) Explicit override (useful for CI / sandbox / embedding into other tools)
    env_root = os.getenv("FAILCORE_PROJECT_ROOT", "").strip()
    if env_root:
        p = Path(env_root).expanduser().resolve()
        _PROJECT_ROOT_CACHE = p
        _debug(f"project root override: {p}")
        return p

    # 1) CWD upward scan
    cwd = Path.cwd()
    root = _find_root_from_path(cwd)
    if root is not None:
        _PROJECT_ROOT_CACHE = root
        _debug(f"project root from CWD: {root}")
        return root

    # 2) entry script dir upward scan
    entry_dir = _entry_script_dir()
    if entry_dir is not None:
        root = _find_root_from_path(entry_dir)
        if root is not None:
            _PROJECT_ROOT_CACHE = root
            _debug(f"project root from entry script: {root}")
            return root

    # 3) Fallback: user home, but isolated by seed to avoid mixing
    # Prefer entry_dir seed, else cwd.
    seed_path = str(entry_dir.resolve()) if entry_dir is not None else str(cwd.resolve())
    fallback = _home_fallback_root(seed_path)
    _PROJECT_ROOT_CACHE = fallback
    _debug(f"project root fallback: {fallback} (seed={seed_path})")
    return fallback


def get_failcore_root() -> Path:
    """
    Get the .failcore directory path.
    Returns:
        Path to .failcore directory (e.g., /project/.failcore/ or ~/.failcore/projects/<hash>/.failcore)
    Note:
        - Does NOT create the directory.
        - Project root is resolved once and cached.
    """
    project_root = find_project_root()
    return project_root / ".failcore"


def format_relative_path(path: Path) -> str:
    """
    Format path as relative to project root for trace display.
    Prefers project-relative paths; falls back to trimming from ".failcore" if present.
    """
    try:
        project_root = find_project_root()
        p = path
        if not isinstance(p, Path):
            p = Path(str(p))

        if p.is_absolute() and _is_relative_to(p, project_root):
            rel_path = p.resolve().relative_to(project_root.resolve())
            return str(rel_path).replace("\\", "/")

        parts = p.parts
        if ".failcore" in parts:
            idx = parts.index(".failcore")
            return "/".join(parts[idx:])

        return str(p).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def to_failcore_relative(path: Path) -> str:
    """
    Convert path to relative path from failcore_root (.failcore directory).
    
    This ensures all paths in trace files are relative to .failcore directory,
    making them portable and avoiding absolute path leakage in trace files.
    
    Args:
        path: Absolute or relative path
    
    Returns:
        Path string relative to failcore_root with forward slashes
    
    Examples:
        >>> to_failcore_relative(Path("/home/user/proj/.failcore/runs/20240101/run_120000/sandbox"))
        'runs/20240101/run_120000/sandbox'
        >>> to_failcore_relative(Path("C:\\proj\\.failcore\\runs\\run_120000\\sandbox"))
        'runs/run_120000/sandbox'
    """
    try:
        failcore_root = get_failcore_root()
        # Resolve to absolute path first
        abs_path = path.resolve() if not path.is_absolute() else path
        # Make relative to failcore_root
        rel_path = abs_path.relative_to(failcore_root)
        return str(rel_path).replace("\\", "/")
    except (ValueError, OSError):
        # Path is outside failcore_root or cannot be resolved
        # Fall back to format_relative_path
        return format_relative_path(path)


@dataclass(frozen=True)
class RunContext:
    """
    Represents a single FailCore run.

    Directory structure:
        <root>/.failcore/runs/<date>/run_<HHMMSSMMM>/
            ├── trace.jsonl
            └── sandbox/
        OR for proxy:
        <root>/.failcore/runs/<date>/proxy_<HHMMSSMMM>/
            ├── proxy.jsonl
    """
    command_name: str
    started_at: datetime
    run_id: str
    root: Path  # .failcore root (NOT project root)

    @property
    def date_str(self) -> str:
        return self.started_at.strftime("%Y%m%d")

    @property
    def time_str(self) -> str:
        return self.started_at.strftime("%H%M%S%f")[:9]  # HHMMSSMMM (包含毫秒前3位)

    @property
    def run_dir_name(self) -> str:
        # Simplified naming: run_<HHMMSSMMM> or proxy_<HHMMSSMMM>
        # Include milliseconds to avoid conflicts in rapid execution
        if self.command_name == "proxy":
            return f"proxy_{self.time_str}"
        return f"run_{self.time_str}"

    @property
    def run_dir(self) -> Path:
        return self.root / "runs" / self.date_str / self.run_dir_name

    @property
    def trace_path(self) -> Path:
        return self.run_dir / "trace.jsonl"

    @property
    def sandbox_path(self) -> Path:
        return self.run_dir / "sandbox"


def _ensure_parent_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def init_run(
    command_name: str = "run",
    *,
    root: Optional[Path] = None,
    started_at: Optional[datetime] = None,
    run_id: Optional[str] = None,
    use_utc: bool = False,
) -> RunContext:
    """
    Create a RunContext (pure; does NOT touch filesystem).

    NOTE:
      - root here means ".failcore" root.
      - If root is None, it is resolved lazily at run-time (NOT import-time).
    """
    if started_at is None:
        started_at = datetime.now(timezone.utc) if use_utc else datetime.now()

    if run_id is None:
        run_id = generate_run_id()

    if root is None:
        root = get_failcore_root()

    return RunContext(
        command_name=command_name,
        started_at=started_at,
        run_id=run_id,
        root=root,
    )


def create_run_directory(ctx: RunContext, *, exist_ok: bool = False) -> Path:
    """
    Create the run directory for a context (explicit side-effect).
    """
    ctx.run_dir.mkdir(parents=True, exist_ok=exist_ok)
    return ctx.run_dir


def create_sandbox(ctx: RunContext, *, exist_ok: bool = True) -> Path:
    """
    Create the per-run sandbox directory (explicit side-effect).
    """
    ctx.sandbox_path.mkdir(parents=True, exist_ok=exist_ok)
    return ctx.sandbox_path


def get_run_directory(command_name: str = "run") -> Path:
    """
    Backward-compatible helper: creates a new run directory and returns its path.
    """
    ctx = init_run(command_name)
    return create_run_directory(ctx, exist_ok=False)


def get_trace_path(command_name: str = "run", custom_path: Optional[str] = None) -> str:
    """
    Backward-compatible helper: returns trace path as string.
    """
    if custom_path:
        trace_file = Path(custom_path)
        _ensure_parent_dir(trace_file)
        return str(trace_file)

    ctx = init_run(command_name)
    create_run_directory(ctx, exist_ok=False)
    return str(ctx.trace_path)


def get_database_path() -> Path:
    """
    Get the default database path.
    
    Returns:
        Path to failcore.db (e.g., /project/.failcore/failcore.db or ~/.failcore/projects/<hash>/failcore.db)
    
    Note:
        - Does NOT create the file or directory.
        - Returns absolute path based on project root detection.
    
    Example:
        >>> db_path = get_database_path()
        >>> print(db_path)
        /home/user/myproject/.failcore/failcore.db
    """
    return get_failcore_root() / "failcore.db"


def reset_project_root_cache() -> None:
    """
    Reset cached project root (useful for testing).
    """
    global _PROJECT_ROOT_CACHE
    _PROJECT_ROOT_CACHE = None


def resolve_and_verify(
    path: Path | str,
    sandbox_root: Path | str,
    allow_symlinks: bool = False,
    check_intermediate_symlinks: bool = True
) -> Tuple[bool, Optional[str], Optional[Path]]:
    """
    Resolve and verify a path is within sandbox with strict security checks.
    
    Security checks:
    1. Resolve path to absolute canonical form
    2. Check if resolved path is within sandbox_root
    3. Optionally reject symlinks (final target or intermediate)
    4. Cross-platform: handle Windows drive letters, UNC paths, Unix absolute paths
    
    Args:
        path: Path to verify (relative or absolute)
        sandbox_root: Sandbox root directory
        allow_symlinks: If False, reject if final path is a symlink
        check_intermediate_symlinks: If True, reject if any intermediate component is a symlink
        
    Returns:
        Tuple of (is_safe, error_message, resolved_path)
        - (True, None, resolved_path) if path is safe
        - (False, error_msg, None) if path is unsafe
        
    Examples:
        >>> resolve_and_verify("/tmp/sandbox/file.txt", "/tmp/sandbox")
        (True, None, Path("/tmp/sandbox/file.txt"))
        
        >>> resolve_and_verify("../etc/passwd", "/tmp/sandbox")
        (False, "Path escapes sandbox", None)
        
        >>> resolve_and_verify("/tmp/sandbox/link", "/tmp/sandbox", allow_symlinks=False)
        (False, "Symlinks not allowed", None)
    """
    try:
        # Convert to Path objects
        path_obj = Path(path)
        sandbox_obj = Path(sandbox_root).resolve()
        
        # Resolve path to absolute canonical form
        # Note: resolve() follows symlinks by default
        try:
            resolved = path_obj.resolve()
        except (OSError, RuntimeError) as e:
            return (False, f"Cannot resolve path: {e}", None)
        
        # Check 1: Final path must be within sandbox
        try:
            resolved.relative_to(sandbox_obj)
        except ValueError:
            return (False, f"Path escapes sandbox: {resolved} not in {sandbox_obj}", None)
        
        # Check 2: Reject if final target is a symlink (if not allowed)
        if not allow_symlinks and path_obj.exists():
            # Check if the ORIGINAL path (before resolve) is a symlink
            try:
                if path_obj.is_symlink():
                    return (False, f"Symlinks not allowed: {path_obj}", None)
            except OSError:
                pass  # If we can't check, continue (file might not exist yet)
        
        # Check 3: Check intermediate components for symlinks (TOCTOU protection)
        if check_intermediate_symlinks and path_obj.exists():
            # Walk up the path and check each component
            current = path_obj
            while current != current.parent:
                try:
                    if current.is_symlink():
                        return (False, f"Intermediate symlink detected: {current}", None)
                except OSError:
                    pass  # Continue if we can't check
                
                # Move to parent
                current = current.parent
                
                # Stop if we've reached sandbox root
                try:
                    current.relative_to(sandbox_obj)
                except ValueError:
                    break  # Outside sandbox, stop checking
        
        # Check 4: Platform-specific checks
        if sys.platform == 'win32':
            # Windows: Check for drive letter changes
            if resolved.drive != sandbox_obj.drive:
                return (False, f"Drive letter mismatch: {resolved.drive} != {sandbox_obj.drive}", None)
            
            # Windows: Check for UNC path escapes
            if resolved.as_posix().startswith('//') and not sandbox_obj.as_posix().startswith('//'):
                return (False, "UNC path not allowed in non-UNC sandbox", None)
        
        # All checks passed
        return (True, None, resolved)
        
    except Exception as e:
        logger.error(f"Unexpected error in resolve_and_verify: {e}", exc_info=True)
        return (False, f"Unexpected error: {e}", None)


def secure_sandbox_path(
    path: Path | str,
    sandbox_root: Path | str,
    operation: str = "access"
) -> Path:
    """
    Securely resolve and verify a path, raising exception if unsafe.
    
    Convenience wrapper around resolve_and_verify() that raises on failure.
    
    Args:
        path: Path to verify
        sandbox_root: Sandbox root directory
        operation: Operation description (for error messages)
        
    Returns:
        Resolved safe path
        
    Raises:
        ValueError: If path is unsafe
        
    Example:
        >>> secure_sandbox_path("file.txt", "/tmp/sandbox", "write")
        Path("/tmp/sandbox/file.txt")
    """
    is_safe, error, resolved = resolve_and_verify(
        path,
        sandbox_root,
        allow_symlinks=False,
        check_intermediate_symlinks=True
    )
    
    if not is_safe:
        raise ValueError(f"Unsafe path for {operation}: {error}")
    
    return resolved
