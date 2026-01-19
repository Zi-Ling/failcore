# failcore/api/context.py
"""
Run context manager
"""

from __future__ import annotations
from contextvars import ContextVar
from typing import Optional, Any, Callable, Dict, List
from pathlib import Path
from datetime import datetime

from failcore.core.types.step import Step, RunContext, generate_run_id
from ..core.executor.executor import Executor, ExecutorConfig
from ..core.tools.registry import ToolRegistry
from ..core.tools.spec import ToolSpec
from ..core.tools.metadata import ToolMetadata
from ..core.trace.recorder import JsonlTraceRecorder, NullTraceRecorder, TraceRecorder
from ..core.validate.loader import load_merged_policy
from ..core.validate.engine import ValidationEngine
from ..core.validate.contracts import Policy
from ..utils.paths import get_failcore_root, get_database_path, find_project_root
from ..utils.path_resolver import PathResolver


# Global context variable for storing current run context
CURRENT_RUN_CONTEXT: ContextVar[Optional["RunCtx"]] = ContextVar(
    "CURRENT_RUN_CONTEXT",
    default=None,
)

# Application-level validator registry (singleton at API layer)
# This is created once and reused across runs for performance.
# Core layer (ValidationEngine) only accepts explicit registry injection.
_APP_REGISTRY: Optional["ValidatorRegistry"] = None
_APP_REGISTRY_LOCK = None

def _get_app_registry() -> "ValidatorRegistry":
    """
    Get or create application-level validator registry.
    
    This registry is created once and reused across runs for performance.
    It is registered at the API layer, not in core, to maintain core extractability.
    
    Returns:
        Application-level ValidatorRegistry instance
    """
    global _APP_REGISTRY, _APP_REGISTRY_LOCK
    
    if _APP_REGISTRY is None:
        import threading
        if _APP_REGISTRY_LOCK is None:
            _APP_REGISTRY_LOCK = threading.Lock()
        
        with _APP_REGISTRY_LOCK:
            if _APP_REGISTRY is None:
                from ..core.validate.registry import ValidatorRegistry
                from ..core.validate.bootstrap import register_builtin_validators
                
                _APP_REGISTRY = ValidatorRegistry()
                register_builtin_validators(_APP_REGISTRY)
                # Note: Plugins can be loaded here if needed
    
    return _APP_REGISTRY


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
        # Cost guardrails
        max_cost_usd: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_usd_per_minute: Optional[float] = None,
        # Guard configuration (per-run)
        guard_config: Optional[Any] = None,  # Optional GuardConfig
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
        
        # Create run context using paths.py utilities
        from ..utils.paths import init_run, create_run_directory
        run_ctx = init_run(command_name="run", run_id=self._run_id)
        default_run_dir = create_run_directory(run_ctx, exist_ok=True)
        
        # Resolve sandbox path with security constraints
        if sandbox is None:
            # Default: run-specific sandbox (isolated per run)
            sandbox_path = default_run_dir / "sandbox"
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
        
        # Store sandbox path for property access
        self._sandbox_path = sandbox_path
        
        # Tool registry
        self._tools = ToolRegistry(sandbox_root=sandbox)
        
        # Load policy and create validation engine if specified
        self._policy_obj = None
        self._validation_engine = None
        if policy:
            try:
                self._policy_obj, self._validation_engine = self._load_policy(policy, strict, sandbox)
            except Exception as e:
                raise ValueError(
                    f"Failed to load policy '{policy}': {e}\n"
                    f"Available policies: {', '.join(self._list_available_policies())}\n"
                    f"Or create a policy file at .failcore/validate/{policy}.yaml"
                ) from e
        
        # Store auto_ingest flag
        self._auto_ingest = auto_ingest
        
        # Store guard_config (per-run guard configuration)
        self._guard_config = guard_config
        
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
        
        # Create cost guardian if budget limits specified
        cost_guardian = None
        cost_estimator = None
        cost_storage = None
        enable_cost_tracking = False
        
        if max_cost_usd or max_tokens or max_usd_per_minute:
            from ..core.cost.guardian import CostGuardian
            from ..core.cost.estimator import CostEstimator
            from ..infra.storage.cost import CostStorage
            
            enable_cost_tracking = True
            cost_estimator = CostEstimator()
            cost_storage = CostStorage()
            
            # Note: CostGuardian only supports max_cost_usd, max_tokens, and max_usd_per_minute
            cost_guardian = CostGuardian(
                max_cost_usd=max_cost_usd,
                max_tokens=max_tokens,
                max_usd_per_minute=max_usd_per_minute,
            )
            
            # Record budget snapshot for audit/replay
            # This captures "what limits were applied" for this run
            cost_storage.insert_budget_snapshot(
                budget_id=f"run_{self._run_id}",
                scope="run",
                run_id=self._run_id,
                max_cost_usd=max_cost_usd,
                max_tokens=max_tokens,
                max_usd_per_minute=max_usd_per_minute,
            )
        
        # Create executor
        # Note: CostStorage is created inside Executor when cost tracking is enabled
        self._executor = Executor(
            guard_config=self._guard_config,
            tools=self._tools,
            recorder=self._recorder,
            validation_engine=self._validation_engine,  # Pass ValidationEngine
            policy=self._policy_obj,
            config=ExecutorConfig(enable_cost_tracking=enable_cost_tracking),
            cost_guardian=cost_guardian,
            cost_estimator=cost_estimator,
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
    
    def _load_policy(self, policy: str, strict: bool, sandbox: str) -> tuple[Optional[Policy], Optional[ValidationEngine]]:
        """
        Load policy from file or preset name and create ValidationEngine.
        
        Policy loading strategy:
        1. Try to load from .failcore/validate/ directory as policy name (e.g., "fs_safe" -> "fs_safe.yaml")
        2. If not found, try common policy names in active.yaml metadata
        3. If not found, fallback to builtin preset templates
        
        Args:
            policy: Policy name or path
            strict: Strict mode flag (affects engine execution, not policy data)
            sandbox: Sandbox root directory path
        
        Returns:
            (Policy object, ValidationEngine instance) or (None, None) if policy not found
        """
        from pathlib import Path
        from ..utils.paths import find_project_root
        
        # Try loading from .failcore/validate/ directory
        project_root = find_project_root()
        policy_dir = project_root / ".failcore" / "validate"
        
        # Strategy 1: Try policy name as filename
        policy_file = policy_dir / f"{policy}.yaml"
        if policy_file.exists():
            from ..core.validate.loader import load_policy
            policy_obj = load_policy(policy_file)
        else:
            # Strategy 2: Try loading active.yaml and check metadata for policy name
            active_file = policy_dir / "active.yaml"
            if active_file.exists():
                from ..core.validate.loader import load_merged_policy
                try:
                    policy_obj = load_merged_policy(project_root)
                    # Check if metadata name matches
                    if policy_obj.metadata.get("name") != policy:
                        # Try to find preset by name
                        policy_obj = self._load_preset_policy(policy)
                except Exception:
                    policy_obj = self._load_preset_policy(policy)
            else:
                # Strategy 3: Use builtin preset
                policy_obj = self._load_preset_policy(policy)
        
        if policy_obj is None:
            # Return None, None to allow policy=None case (no validation)
            return None, None
        
        # Inject runtime context (sandbox_root) into policy config
        # This is runtime binding, not policy modification
        if sandbox:
            policy_obj = self._inject_sandbox_root(policy_obj, sandbox)
        
        # Create ValidationEngine with strict mode
        # Strict mode affects execution behavior, not policy data
        # Use application-level registry (singleton at API layer) for performance
        registry = _get_app_registry()
        engine = ValidationEngine(
            registry=registry,
            policy=policy_obj,
            strict_mode=strict,
        )
        
        return policy_obj, engine
    
    def _load_preset_policy(self, policy_name: str) -> Optional[Policy]:
        """Load policy from builtin presets."""
        from ..core.validate.templates import get_preset
        
        # Map common policy names to preset names
        preset_map = {
            "safe": "default_safe",
            "fs_safe": "fs_safe",
            "net_safe": "net_safe",
            "shadow": "shadow_mode",
            "permissive": "permissive",
        }
        
        preset_name = preset_map.get(policy_name, policy_name)
        preset_policy = get_preset(preset_name)
        
        if preset_policy:
            # Return a copy to avoid modifying the preset
            return preset_policy.model_copy(deep=True)
        
        return None
    
    def _inject_sandbox_root(self, policy: Policy, sandbox_root: str) -> Policy:
        """
        Inject sandbox_root into policy config (runtime binding, returns new policy).
        
        This creates a new Policy object with sandbox_root injected into validator configs.
        The original policy is not modified.
        """
        # Create a deep copy
        new_policy = policy.model_copy(deep=True)
        
        # Inject sandbox_root into path_traversal validator config
        if "security_path_traversal" in new_policy.validators:
            config = new_policy.validators["security_path_traversal"]
            if config.config is None:
                config.config = {}
            config.config["sandbox_root"] = sandbox_root
        
        return new_policy
    
    def _list_available_policies(self) -> list[str]:
        """List available policy names."""
        from ..core.validate.templates import list_presets
        return list_presets()
    
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
            
            # Note: Validation is now handled by ValidationEngine via StepValidator
            # Tool registration only registers the tool with metadata
        else:
            self._tools.register(tool_name, fn)
        
        return fn
    
    def call(self, tool: str, _meta: Optional[Dict[str, Any]] = None, **params: Any) -> Any:
        """
        Call a tool (synchronous)
        
        Args:
            tool: Tool name
            _meta: Optional metadata (for cost overrides, etc.)
            **params: Tool parameters
        
        Returns:
            Tool execution result
        
        Raises:
            FailCoreError: On execution failure
        
        Example:
            >>> result = ctx.call("write_file", path="a.txt", content="hi")
            >>> result = ctx.call("expensive_tool", task="x", _meta={"cost_usd": 0.50})
        """
        # Generate step_id
        self._step_counter += 1
        step_id = f"s{self._step_counter:04d}"
        
        # Create step
        step = Step(
            id=step_id,
            tool=tool,
            params=params,
            meta=_meta or {}
        )
        
        # Execute
        result = self._executor.execute(step, self._ctx)
        
        # Raise error on failure
        from failcore.core.types.step import StepStatus
        if result.status == StepStatus.OK:
            return result.output.value if result.output else None
        
        # Raise unified error
        from ..core.errors import FailCoreError
        raise FailCoreError.from_tool_result(result)
    
    async def acall(self, tool: str, **params: Any) -> Any:
        """
        Call a tool (asynchronous) - Async Bridge Implementation
        
        Architecture:
        - Strict async/sync separation via inspect.iscoroutinefunction
        - Context preservation via contextvars.copy_context()
        - Unified error handling with ASYNC_SYNC_MISMATCH detection
        
        Args:
            tool: Tool name
            **params: Tool parameters
        
        Returns:
            Tool execution result
        
        Raises:
            FailCoreError: On execution failure or async/sync mismatch
        
        Example:
            >>> result = await ctx.acall("write_file", path="a.txt", content="hi")
        """
        import asyncio
        import inspect
        import contextvars
        
        # Check if tool function exists
        fn = self._tools.get(tool)
        if fn is None:
            from ..core.errors import FailCoreError, codes
            registered_tools = self._tools.list()
            raise FailCoreError(
                message=f"Tool '{tool}' not found in current context",
                error_code=codes.TOOL_NOT_FOUND,
                error_type="REGISTRY_ERROR",
                phase="execute",
                details={"tool_name": tool, "registered_tools": registered_tools},
                suggestion=f"Register the tool first: guard({tool}, risk='medium', effect='fs')",
                hint=f"Available tools: {', '.join(registered_tools) if registered_tools else 'none'}",
            )
        
        # Strict async/sync type checking
        is_async = inspect.iscoroutinefunction(fn)
        
        if is_async:
            # Tool is async - currently not fully supported
            # For now, raise clear error
            from ..core.errors import FailCoreError, codes
            raise FailCoreError(
                message=f"Async tool '{tool}' called via acall() - async tools not yet fully supported",
                error_code=codes.NOT_IMPLEMENTED,
                error_type="ASYNC_ERROR",
                phase="execute",
                details={"tool_name": tool, "tool_is_async": True},
                suggestion="Use synchronous tools for now. Async tool execution will be added in future versions.",
                hint="Convert your tool to synchronous or wait for async executor support",
            )
        else:
            # Tool is sync - run in executor with context preservation
            loop = asyncio.get_event_loop()
            
            # Copy current context to preserve run() session across threads
            ctx_copy = contextvars.copy_context()
            
            # Run sync tool in thread pool with context
            return await loop.run_in_executor(
                None,
                lambda: ctx_copy.run(self.call, tool, **params)
            )
    
    def close(self) -> None:
        """
        Close context and cleanup resources
        
        If auto_ingest=True, automatically ingest trace to database
        """
        # Update run status to 'completed' before closing
        if hasattr(self, '_executor') and hasattr(self._executor, 'services') and self._executor.services.cost_storage:
            try:
                self._executor.services.cost_storage.upsert_run(
                    run_id=self._run_id,
                    status="completed",
                )
            except Exception:
                # Don't fail cleanup if status update fails
                pass
        
        # Close recorder first to flush trace
        if hasattr(self._recorder, 'close'):
            try:
                self._recorder.close()
            except Exception:
                pass
        
        # Analysis features (drift, optimizer) - controlled by config
        from ..config.analysis import is_drift_enabled, is_optimizer_enabled
        
        if self._trace_path and Path(self._trace_path).exists():
            # Drift analysis (if enabled by config)
            if is_drift_enabled():
                # Idempotent: only compute if not already computed
                if not hasattr(self, '_drift_result') or self._drift_result is None:
                    try:
                        from ..core.replay.drift import compute_drift
                        # compute_drift() extracts baseline from the trace itself:
                        # - Baseline = first occurrence of each tool's parameters
                        # - Drift = comparison of subsequent steps against baseline
                        drift_result = compute_drift(self._trace_path)
                        # Store drift result in context (can be accessed via property if needed)
                        self._drift_result = drift_result
                    except Exception:
                        # Don't fail cleanup if drift computation fails
                        self._drift_result = None
                        pass
            
            # Optimizer analysis (if enabled by config)
            if is_optimizer_enabled():
                # Idempotent: only compute if not already computed
                if not hasattr(self, '_optimization_result') or self._optimization_result is None:
                    try:
                        from ..core.optimizer import OptimizationAdvisor
                        advisor = OptimizationAdvisor()
                        # Extract call records from trace
                        calls = self._extract_calls_from_trace()
                        if calls:
                            suggestions = advisor.analyze_trace(calls)
                            self._optimization_result = {
                                "suggestions": [s.to_dict() for s in suggestions],
                                "report": advisor.generate_report(calls),
                            }
                        else:
                            self._optimization_result = None
                    except Exception:
                        # Don't fail cleanup if optimizer computation fails
                        self._optimization_result = None
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
    def sandbox_root(self) -> Path:
        """Get sandbox root directory"""
        return self._sandbox_path
    
    @property
    def cost_storage(self):
        """Get the cost storage instance used by this context"""
        if hasattr(self, '_executor') and self._executor and hasattr(self._executor, 'services'):
            return self._executor.services.cost_storage
        return None
    
    @property
    def cost_guardian(self):
        """Get the cost guardian instance used by this context"""
        if hasattr(self, '_executor') and self._executor and hasattr(self._executor, 'services'):
            return self._executor.services.cost_guardian
        return None
    
    @property
    def run_id(self) -> str:
        """Get run ID"""
        return self._run_id
    
    @property
    def drift_result(self) -> Optional[Any]:
        """Get the drift analysis result for this run"""
        return getattr(self, '_drift_result', None)
    
    @property
    def optimization_result(self) -> Optional[Dict[str, Any]]:
        """Get the optimization analysis result for this run"""
        return getattr(self, '_optimization_result', None)
    
    def _extract_calls_from_trace(self) -> List[Dict[str, Any]]:
        """
        Extract call records from trace file for optimizer analysis
        
        Returns:
            List of call records with format:
            {
                "step_id": str,
                "tool_name": str,
                "params": Dict[str, Any],
                "result": Any (optional),
            }
        """
        import json
        
        if not self._trace_path or not Path(self._trace_path).exists():
            return []
        
        calls = []
        step_results = {}  # step_id -> result
        
        try:
            with open(self._trace_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        event = json.loads(line)
                        evt = event.get("event", {})
                        evt_type = evt.get("type")
                        
                        # Extract from ATTEMPT events
                        if evt_type == "ATTEMPT":
                            step = evt.get("step", {})
                            tool_name = step.get("tool", "")
                            step_id = step.get("id", "")
                            
                            if not tool_name:
                                continue
                            
                            # Extract parameters (similar to drift extractor)
                            params = self._extract_params_from_event(evt, step)
                            
                            # Create call record (result will be filled from RESULT)
                            call = {
                                "step_id": step_id,
                                "tool_name": tool_name,
                                "params": params,
                                "result": None,  # Will be filled from RESULT
                            }
                            calls.append(call)
                        
                        # Extract results from RESULT events
                        elif evt_type == "RESULT":
                            step = evt.get("step", {})
                            step_id = step.get("id", "")
                            data = evt.get("data", {})
                            output = data.get("output")
                            
                            # Store result for later matching
                            if step_id and output:
                                step_results[step_id] = output
                    
                    except (json.JSONDecodeError, KeyError):
                        # Skip malformed events
                        continue
            
            # Match results with calls
            for call in calls:
                step_id = call["step_id"]
                if step_id in step_results:
                    call["result"] = step_results[step_id]
        
        except Exception:
            # Return empty list on any error
            return []
        
        return calls
    
    def _extract_params_from_event(self, event: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters from event data (similar to drift extractor)
        
        Tries multiple paths to find parameters:
        1. event.data.payload.input.summary (v0.1.2 format)
        2. event.data.payload.input (fallback)
        3. step.params (legacy format)
        4. step.data (alternative)
        """
        data = event.get("data", {})
        payload = data.get("payload", {})
        input_data = payload.get("input", {})
        
        # Try summary first (v0.1.2 format)
        if "summary" in input_data:
            params = input_data["summary"]
            if isinstance(params, dict):
                return params
        
        # Try direct input
        if isinstance(input_data, dict) and input_data:
            # Check if it looks like params (not just metadata)
            if not all(k in ("mode", "hash", "summary") for k in input_data.keys()):
                return input_data
        
        # Try step.params (legacy format)
        if "params" in step:
            params = step["params"]
            if isinstance(params, dict):
                return params
        
        # Try step.data
        step_data = step.get("data", {})
        if isinstance(step_data, dict) and step_data:
            return step_data
        
        return {}


def get_current_context() -> Optional[RunCtx]:
    """
    Get current run context
    
    Returns:
        Current context, or None if not within a run() block
    """
    return CURRENT_RUN_CONTEXT.get()
