# failcore/api/context.py
"""
Run context manager
"""

from __future__ import annotations
from contextvars import ContextVar
from typing import Optional, Any, Callable, Dict
from pathlib import Path
from datetime import datetime

from ..core.step import Step, RunContext, StepResult, generate_step_id, generate_run_id
from ..core.executor.executor import Executor, ExecutorConfig
from ..core.tools.registry import ToolRegistry
from ..core.tools.spec import ToolSpec
from ..core.tools.metadata import ToolMetadata
from ..core.trace.recorder import JsonlTraceRecorder, NullTraceRecorder, TraceRecorder
from ..core.validate.validator import ValidatorRegistry
from ..core.validate.presets import ValidationPreset
from ..core.policy.policy import Policy
from ..utils.paths import get_failcore_root, get_database_path, find_project_root
from ..utils.path_resolver import PathResolver


# Global context variable for storing current run context
CURRENT_RUN_CONTEXT: ContextVar[Optional["RunCtx"]] = ContextVar(
    "CURRENT_RUN_CONTEXT",
    default=None,
)


class RunCtx:
    """
    Run Context - unified execution context for tool calls
    
    Provides tool registration, invocation, tracing, and validation within
    a single context manager scope.
    
    Features:
    - ctx.tool(fn): Register a tool function
    - ctx.call(name, **params): Invoke a tool
    - ctx.trace_path: Get trace file path
    - Automatically sets as global context for @guard() decorator
    
    Example:
        >>> with run(policy="fs_safe", sandbox="./data") as ctx:
        ...     ctx.tool(write_file)
        ...     ctx.call("write_file", path="a.txt", content="hi")
        ...     print(ctx.trace_path)
    """
    
    def __init__(
        self,
        policy: Optional[str] = None,
        sandbox: Optional[str] = None,
        trace: str = "auto",
        strict: bool = True,
        run_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        auto_ingest: bool = True,
        allow_outside_root: bool = False,
        allowed_trace_roots: Optional[list] = None,
        allowed_sandbox_roots: Optional[list] = None,
    ):
        """
        Create a new run context with intelligent path resolution.
        
        See run() function docstring for detailed path resolution rules.
        """
        # Generate run_id first
        self._run_id = run_id or generate_run_id()
        
        # Initialize path resolver
        project_root = find_project_root()
        path_resolver = PathResolver(
            project_root=project_root,
            allow_outside_root=allow_outside_root,
        )
        
        failcore_root = get_failcore_root()
        
        # Create default run directory for this context
        now = datetime.now()
        date = now.strftime("%Y%m%d")
        time = now.strftime("%H%M%S")
        default_run_dir = failcore_root / "runs" / date / f"{self._run_id}_{time}"
        
        # Resolve sandbox path with security constraints
        if sandbox is None:
            # Default: project-level shared sandbox
            sandbox_path = failcore_root / "sandbox"
        else:
            default_sandbox_loc = default_run_dir / "sandbox"
            sandbox_path = path_resolver.resolve(
                sandbox,
                default_sandbox_loc,
                'sandbox',
                allowed_sandbox_roots,
            )
        
        # Create sandbox directory
        sandbox_path.mkdir(parents=True, exist_ok=True)
        sandbox = str(sandbox_path)
        
        # Tool registry
        self._tools = ToolRegistry(sandbox_root=sandbox)
        
        # Validator registry
        self._validator = ValidatorRegistry()
        
        # Load policy validator if specified
        if policy:
            self._load_policy_validator(policy, strict)
        
        # Store auto_ingest flag
        self._auto_ingest = auto_ingest
        
        # Handle trace path with security constraints
        if trace == "auto":
            # Auto: default run directory
            default_run_dir.mkdir(parents=True, exist_ok=True)
            trace_path = default_run_dir / "trace.jsonl"
            self._recorder: TraceRecorder = JsonlTraceRecorder(str(trace_path))
            self._trace_path = trace_path.as_posix()
        elif trace is None:
            # Disabled
            self._recorder: TraceRecorder = NullTraceRecorder()
            self._trace_path = None
        else:
            # Custom path: resolve with security
            default_trace_loc = default_run_dir / "trace"
            trace_path = path_resolver.resolve(
                trace,
                default_trace_loc,
                'trace',
                allowed_trace_roots,
            )
            
            # Create parent directory
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._recorder: TraceRecorder = JsonlTraceRecorder(str(trace_path))
            self._trace_path = trace_path.as_posix()
        
        # Create executor
        policy_obj = None  # TODO: create Policy object from policy parameter
        self._executor = Executor(
            tools=self._tools,
            recorder=self._recorder,
            validator=self._validator,
            policy=policy_obj,
            config=ExecutorConfig()
        )
        
        # Run context
        sandbox_rel = None
        if sandbox:
            sandbox_path = Path(sandbox)
            if sandbox_path.is_absolute():
                try:
                    sandbox_rel = sandbox_path.relative_to(Path.cwd()).as_posix()
                except ValueError:
                    sandbox_rel = Path(sandbox).as_posix()
            else:
                sandbox_rel = Path(sandbox).as_posix()
        
        self._ctx = RunContext(
            run_id=self._run_id,
            sandbox_root=sandbox_rel,
            tags=tags or {}
        )
        
        # Step counter
        self._step_counter = 0
    
    def _load_policy_validator(self, policy: str, strict: bool):
        """
        Load validator for the specified policy.
        
        Args:
            policy: Policy name
            strict: Strict mode flag
        """
        if policy == "safe":
            # Combined preset: fs_safe + net_safe
            from ..presets.validators import fs_safe, net_safe
            fs_validator = fs_safe(strict=strict)
            net_validator = net_safe(strict=strict)
            # TODO: implement proper validator merging
            # For now, just use fs_safe (most common case)
            self._validator = fs_validator
        elif policy == "fs_safe":
            from ..presets.validators import fs_safe
            validator = fs_safe(strict=strict)
            self._validator = validator
        elif policy == "net_safe":
            from ..presets.validators import net_safe
            validator = net_safe(strict=strict)
            self._validator = validator
        else:
            # Unknown policy: leave validator as-is
            pass
    
    def tool(self, fn: Callable[..., Any], metadata: Optional[ToolMetadata] = None) -> Callable[..., Any]:
        """
        Register a tool function
        
        Args:
            fn: Tool function
            metadata: Optional tool metadata
        
        Returns:
            Original function (unmodified)
        
        Example:
            >>> ctx.tool(write_file)
            >>> ctx.tool(read_file, metadata=ToolMetadata(...))
        """
        tool_name = fn.__name__
        
        if metadata is not None:
            spec = ToolSpec(
                name=tool_name,
                fn=fn,
                description="",
                tool_metadata=metadata,
            )
            self._tools.register_tool(spec, auto_assemble=True)
            
            # Sync validators
            preconditions = self._tools.get_preconditions(tool_name)
            postconditions = self._tools.get_postconditions(tool_name)
            for precond in preconditions:
                self._validator.register_precondition(tool_name, precond)
            for postcond in postconditions:
                self._validator.register_postcondition(tool_name, postcond)
        else:
            self._tools.register(tool_name, fn)
        
        return fn
    
    def call(self, tool: str, **params: Any) -> Any:
        """
        Call a tool
        
        Args:
            tool: Tool name
            **params: Tool parameters
        
        Returns:
            Tool execution result
        
        Raises:
            FailCoreError: On execution failure
        
        Example:
            >>> result = ctx.call("write_file", path="a.txt", content="hi")
        """
        # Generate step_id
        self._step_counter += 1
        step_id = f"s{self._step_counter:04d}"
        
        # Create step
        step = Step(
            id=step_id,
            tool=tool,
            params=params
        )
        
        # Execute
        result = self._executor.execute(step, self._ctx)
        
        # Raise error on failure
        from ..core.step import StepStatus
        if result.status == StepStatus.OK:
            return result.output.value if result.output else None
        
        # Raise unified error
        from ..core.errors import FailCoreError
        raise FailCoreError.from_tool_result(result)
    
    def close(self) -> None:
        """
        Close context and cleanup resources
        
        If auto_ingest=True, automatically ingest trace to database
        """
        # Close recorder first to flush trace
        if hasattr(self._recorder, 'close'):
            try:
                self._recorder.close()
            except Exception:
                pass
        
        # Auto-ingest trace to database
        if self._auto_ingest and self._trace_path:
            self._ingest_trace()
    
    def _ingest_trace(self) -> None:
        """
        Internal method: Ingest trace to database.
        
        Called automatically if auto_ingest=True.
        Failures are silently logged to avoid breaking context cleanup.
        """
        try:
            from ..infra.storage import SQLiteStore, TraceIngestor
            
            # Check if trace file exists and has content
            if not Path(self._trace_path).exists():
                return
            
            file_size = Path(self._trace_path).stat().st_size
            if file_size == 0:
                return
            
            # Default database path (uses project root detection)
            db_path = str(get_database_path())
            
            # Ensure directory exists
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Ingest trace
            with SQLiteStore(db_path) as store:
                store.init_schema()
                ingestor = TraceIngestor(store)
                stats = ingestor.ingest_file(self._trace_path, skip_if_exists=True)
        
        except ImportError:
            # Storage module not available - skip silently
            pass
        except Exception as e:
            # Don't fail context close due to ingest errors
            # Users can manually ingest later if needed
            import sys
            if hasattr(sys, 'stderr'):
                print(f"Warning: Failed to auto-ingest trace: {e}", file=sys.stderr)
    
    def __enter__(self) -> RunCtx:
        """Support context manager"""
        # Set as global current context
        self._token = CURRENT_RUN_CONTEXT.set(self)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Support context manager"""
        # Restore previous context
        CURRENT_RUN_CONTEXT.reset(self._token)
        self.close()
    
    @property
    def trace_path(self) -> Optional[str]:
        """Get trace file path"""
        return self._trace_path
    
    @property
    def run_id(self) -> str:
        """Get run ID"""
        return self._run_id


def get_current_context() -> Optional[RunCtx]:
    """
    Get current run context
    
    Returns:
        Current context, or None if not within a run() block
    """
    return CURRENT_RUN_CONTEXT.get()
