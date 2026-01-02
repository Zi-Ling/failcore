# failcore/utils/paths.py
"""
Shared path utilities for FailCore.

Design goals:
- Deterministic and explicit: creating a run is a deliberate action.
- No hidden side-effects in "get_*" helpers (they don't create directories).
- Unified naming: <run_id>_<HHMMSS>_<command>
- Prefer pathlib.Path throughout; convert to str only at CLI edges if needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from failcore.core.step import generate_run_id


DEFAULT_ROOT = Path(".failcore")


@dataclass(frozen=True)
class RunContext:
    """
    Represents a single FailCore run.

    A run directory is uniquely determined by (run_id, started_at, command_name).
    
    Directory structure:
        .failcore/runs/<date>/<run_id>_<HHMMSS>_<command>/
            ├── trace.jsonl
            └── sandbox/          (per-run isolated workspace)
    
    Example:
        .failcore/runs/20260101/run_a3b5c7d9e1f2_143025_mcp/trace.jsonl
        .failcore/runs/20260101/run_a3b5c7d9e1f2_143025_mcp/sandbox/
    """
    command_name: str
    started_at: datetime
    run_id: str
    root: Path = DEFAULT_ROOT

    @property
    def date_str(self) -> str:
        return self.started_at.strftime("%Y%m%d")

    @property
    def time_str(self) -> str:
        # HHMMSS format for readability (run_id provides uniqueness)
        return self.started_at.strftime("%H%M%S")

    @property
    def run_dir_name(self) -> str:
        # Format: <run_id>_<HHMMSS>_<command>
        return f"{self.run_id}_{self.time_str}_{self.command_name}"

    @property
    def run_dir(self) -> Path:
        # .failcore/runs/<date>/<run_id>_<HHMMSS>_<command>/
        return self.root / "runs" / self.date_str / self.run_dir_name

    @property
    def trace_path(self) -> Path:
        return self.run_dir / "trace.jsonl"
    
    @property
    def sandbox_path(self) -> Path:
        """
        Per-run isolated sandbox directory.
        
        Returns:
            Path to sandbox directory (not automatically created).
        
        Usage:
            ctx = init_run("mcp")
            sandbox = create_sandbox(ctx)  # explicit creation
            # or
            ctx.sandbox_path.mkdir(parents=True, exist_ok=True)
        """
        return self.run_dir / "sandbox"


def _ensure_parent_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def init_run(
    command_name: str = "run",
    *,
    root: Path = DEFAULT_ROOT,
    started_at: Optional[datetime] = None,
    run_id: Optional[str] = None,
    use_utc: bool = False,
) -> RunContext:
    """
    Create a RunContext (pure; does NOT touch filesystem).

    Args:
        command_name: command name ("mcp", "replay", "sample", etc.)
        root: base directory (default: .failcore)
        started_at: explicit timestamp (useful for tests / deterministic runs)
        run_id: explicit run_id (useful for tests; auto-generated if None)
        use_utc: if True, uses UTC time; otherwise local time

    Returns:
        RunContext
    """
    if started_at is None:
        if use_utc:
            started_at = datetime.now(timezone.utc)
        else:
            started_at = datetime.now()
    
    if run_id is None:
        run_id = generate_run_id()
    
    return RunContext(
        command_name=command_name,
        started_at=started_at,
        run_id=run_id,
        root=root,
    )


def create_run_directory(ctx: RunContext, *, exist_ok: bool = False) -> Path:
    """
    Create the run directory for a context (explicit side-effect).

    Args:
        ctx: RunContext
        exist_ok: if False, raise FileExistsError on collision (recommended)

    Returns:
        Path to created run directory
    """
    ctx.run_dir.mkdir(parents=True, exist_ok=exist_ok)
    return ctx.run_dir


def create_sandbox(ctx: RunContext, *, exist_ok: bool = True) -> Path:
    """
    Create the per-run sandbox directory (explicit side-effect).

    Args:
        ctx: RunContext
        exist_ok: if False, raise FileExistsError on collision

    Returns:
        Path to created sandbox directory
    
    Example:
        ctx = init_run("mcp")
        create_run_directory(ctx)
        sandbox = create_sandbox(ctx)
        # Now tools can write to: sandbox / "output.txt"
    """
    ctx.sandbox_path.mkdir(parents=True, exist_ok=exist_ok)
    return ctx.sandbox_path


def get_run_directory(command_name: str = "run") -> Path:
    """
    Backward-compatible helper:
    Create a new run directory and return its path.

    NOTE: This function has side-effects (it creates dirs). Prefer:
      ctx = init_run(...)
      create_run_directory(ctx)
      ctx.run_dir
    """
    ctx = init_run(command_name)
    return create_run_directory(ctx, exist_ok=False)


def get_trace_path(command_name: str = "run", custom_path: Optional[str] = None) -> str:
    """
    Backward-compatible helper:
    Get a trace path as a string for legacy call sites.

    - If custom_path is provided, uses it and ensures parent dir exists.
    - Otherwise, creates a new run directory and returns its trace.jsonl path.

    NOTE: If you want NO side-effects, use:
      ctx = init_run(...)
      ctx.trace_path  (Path)
    """
    if custom_path:
        trace_file = Path(custom_path)
        _ensure_parent_dir(trace_file)
        return str(trace_file)

    ctx = init_run(command_name)
    create_run_directory(ctx, exist_ok=False)
    return str(ctx.trace_path)
