# failcore/core/executor/stages/dispatch.py
"""
Dispatch Stage - tool execution with optional ProcessExecutor and SideEffectProbe
"""

from typing import Optional, Any, List

from ..state import ExecutionState, ExecutionServices
from failcore.core.types.step import StepResult
from ...trace import ExecutionPhase


class DispatchStage:
    """Stage 6: Execute tool (with optional ProcessExecutor and SideEffectProbe)"""
    
    def __init__(self, process_executor: Optional[Any] = None):
        """
        Initialize dispatch stage
        
        Args:
            process_executor: Optional ProcessExecutor for isolated execution
        """
        self.process_executor = process_executor
    
    def execute(
        self,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Optional[StepResult]:
        """
        Execute tool function
        
        Args:
            state: Execution state
            services: Execution services
        
        Returns:
            StepResult if execution fails, None if successful
        
        Note:
            - Sets state.output (normalized)
            - Sets state.actual_usage (if extracted)
            - Can use ProcessExecutor for isolation
            - Can use SideEffectProbe for side-effect detection
        """
        # Get tool function
        fn = services.tools.get(state.step.tool)
        if fn is None:
            return services.failure_builder.fail(
                state=state,
                error_code="TOOL_NOT_FOUND",
                message=f"Tool not found: {state.step.tool}",
                phase=ExecutionPhase.EXECUTE,
            )
        
        # 步骤2：获取有效超时（支持优先级）
        timeout = None
        timeout_metadata = {}
        if hasattr(services, 'executor_config') and services.executor_config:
            config = services.executor_config
            # 获取工具 spec（未来支持 tool-level timeout）
            tool_spec = services.tools.get_tool_spec(state.step.tool) if hasattr(services.tools, 'get_tool_spec') else None
            timeout, timeout_metadata = config.get_effective_timeout(
                step_params=state.step.params,
                tool_spec=tool_spec
            )
            
            # 步骤2要求：如果被 clamp，记录到 trace/audit
            if timeout_metadata.get("clamped"):
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Step {state.step.id} timeout clamped: {timeout_metadata['clamp_reason']}"
                )
                
                # 记录 clamp 事件到 trace（可选但推荐）
                if hasattr(services.recorder, 'next_seq'):
                    from ...trace.events import EventType, TraceEvent, LogLevel, utc_now_iso
                    
                    seq = services.recorder.next_seq()
                    clamp_event = TraceEvent(
                        schema="failcore.trace.v0.1.3",
                        seq=seq,
                        ts=utc_now_iso(),
                        level=LogLevel.WARN,
                        event={
                            "type": "TIMEOUT_CLAMPED",
                            "severity": "warn",
                            "step": {
                                "id": state.step.id,
                                "tool": state.step.tool,
                            },
                            "data": timeout_metadata,
                        },
                        run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
                    )
                    try:
                        services.recorder.record(clamp_event)
                    except Exception:
                        pass  # Non-fatal
        
        try:
            # Optionally use ProcessExecutor for isolation
            if self.process_executor:
                result = self.process_executor.execute(fn, state.step.params, state.ctx.run_id)
                if not result.get("ok", False):
                    error = result.get("error", {})
                    return services.failure_builder.fail(
                        state=state,
                        error_code=error.get("code", "TOOL_EXECUTION_FAILED"),
                        message=error.get("message", "Tool execution failed"),
                        phase=ExecutionPhase.EXECUTE,
                    )
                out = result.get("result")
            else:
                # Direct execution with timeout
                if timeout:
                    out = self._execute_with_timeout(fn, state.step.params, timeout, state, services)
                else:
                    out = fn(**state.step.params)
            
            # Normalize output
            output = services.output_normalizer.normalize(out)
            state.output = output
            
            # Extract actual usage from tool output (if available)
            if services.usage_extractor:
                actual_usage, parse_error = services.usage_extractor.extract(
                    tool_output=out,
                    run_id=state.ctx.run_id,
                    step_id=state.step.id,
                    tool_name=state.step.tool,
                )
                if actual_usage:
                    state.actual_usage = actual_usage
                elif parse_error:
                    # Record parse error to trace (debug level, non-fatal)
                    # Note: Parse errors are non-fatal, just log for debugging
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Usage extraction failed for step {state.step.id}: {parse_error}")
            
            # Detect and record side-effects (post-execution observation)
            observed = self._detect_and_record_side_effects(state, services, out)
            state.observed_side_effects = observed
            
            # Register spawned PIDs in process registry (for ownership tracking)
            if services.process_registry:
                self._register_spawned_pids(state, services, out)
            
            # Mark taint tags for source tools (post-execution)
            if services.taint_engine and services.taint_store:
                self._mark_taint_tags(state, services, output)
            
            return None  # Continue to next stage
        
        except TimeoutError as e:
            # 步骤1：超时语义落地 - 统一的结果模型
            import logging
            import time
            logger = logging.getLogger(__name__)
            logger.error(f"Step {state.step.id} timed out: {e}")
            
            # Return TIMEOUT result (distinct from BLOCKED or FAILED)
            from failcore.core.types.step import StepStatus, StepResult, StepError
            from failcore.core.types.step import utc_now_iso
            
            # Calculate timestamps and duration from ExecutionState
            finished_at = utc_now_iso()
            started_at = state.started_at  # From ExecutionState
            # Calculate duration from t0 (performance counter)
            elapsed = time.time() - state.t0
            duration_ms = max(int(elapsed * 1000), int(timeout * 1000), 100)  # At least timeout duration
            
            return StepResult(
                step_id=state.step.id,
                tool=state.step.tool,
                status=StepStatus.TIMEOUT,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                output=None,
                error=StepError(
                    error_code="STEP_TIMEOUT",  # 使用 error_code 而不是 code
                    message=f"Step execution exceeded timeout of {timeout}s",
                    detail={
                        "timeout_seconds": timeout,  # 步骤1要求：必须包含此字段
                        "tool": state.step.tool,
                        "step_id": state.step.id,
                        "phase": "execute",
                    },
                ),
            )
        
        except Exception as e:
            import traceback
            code = "TOOL_RAISED"
            msg = f"{type(e).__name__}: {e}"
            detail = {}
            if hasattr(services.failure_builder, 'summarizer') and services.failure_builder.summarizer:
                # Include stack if config allows
                detail["stack"] = traceback.format_exc()
            
            return services.failure_builder.fail(
                state=state,
                error_code=code,
                message=msg,
                phase=ExecutionPhase.EXECUTE,
                detail=detail,
            )
    
    def _detect_and_record_side_effects(
        self,
        state: ExecutionState,
        services: ExecutionServices,
        tool_output: Any,
    ) -> List[Any]:
        """
        Detect and record side-effects from tool execution
        
        Args:
            state: Execution state
            services: Execution services
            tool_output: Tool output (may contain side-effect hints)
        
        Returns:
            List of SideEffectEvent objects observed
        """
        from failcore.core.guards.effects.detection import (
            detect_filesystem_side_effect,
            detect_network_side_effect,
            detect_exec_side_effect,
        )
        from failcore.core.guards.effects.events import SideEffectEvent
        from ...trace.events import EventType, TraceEvent, LogLevel, utc_now_iso
        from failcore.core.guards.effects.side_effects import get_category_for_type
        
        # Detect side-effects from tool name and params
        side_effect_events = []
        side_effects = []
        
        # Filesystem side-effects
        fs_read = detect_filesystem_side_effect(state.step.tool, state.step.params, "read")
        if fs_read:
            side_effects.append((fs_read, state.step.params.get("path") or state.step.params.get("file")))
        
        fs_write = detect_filesystem_side_effect(state.step.tool, state.step.params, "write")
        if fs_write:
            side_effects.append((fs_write, state.step.params.get("path") or state.step.params.get("file")))
        
        fs_delete = detect_filesystem_side_effect(state.step.tool, state.step.params, "delete")
        if fs_delete:
            side_effects.append((fs_delete, state.step.params.get("path") or state.step.params.get("file")))
        
        # Network side-effects
        net_egress = detect_network_side_effect(state.step.tool, state.step.params, "egress")
        if net_egress:
            side_effects.append((net_egress, state.step.params.get("url") or state.step.params.get("host")))
        
        # Exec side-effects
        exec_effect = detect_exec_side_effect(state.step.tool, state.step.params)
        if exec_effect:
            side_effects.append((exec_effect, state.step.params.get("command") or state.step.params.get("cmd")))
        
        # Record each detected side-effect
        for side_effect_type, target in side_effects:
            if side_effect_type:
                # Create SideEffectEvent
                side_effect_event = SideEffectEvent(
                    type=side_effect_type,
                    target=target,
                    tool=state.step.tool,
                    step_id=state.step.id,
                )
                side_effect_events.append(side_effect_event)
                
                # Record to trace
                if hasattr(services.recorder, 'next_seq') and state.seq is not None:
                    seq = services.recorder.next_seq()
                    category = get_category_for_type(side_effect_type).value
                    
                    event = TraceEvent(
                        schema="failcore.trace.v0.1.3",
                        seq=seq,
                        ts=utc_now_iso(),
                        level=LogLevel.INFO,
                        event={
                            "type": EventType.SIDE_EFFECT_APPLIED.value,
                            "severity": "ok",
                            "step": {
                                "id": state.step.id,
                                "tool": state.step.tool,
                                "attempt": state.attempt,
                            },
                            "data": {
                                "side_effect": {
                                    "type": side_effect_type.value,
                                    "target": target,
                                    "category": category,
                                    "tool": state.step.tool,
                                    "step_id": state.step.id,
                                    "metadata": {},
                                }
                            },
                        },
                        run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
                    )
                    
                    try:
                        services.recorder.record(event)
                    except Exception:
                        # Don't fail execution if side-effect recording fails
                        pass
        
        state.observed_side_effects = side_effect_events
        return side_effect_events
    
    def _mark_taint_tags(
        self,
        state: ExecutionState,
        services: ExecutionServices,
        output: Any,
    ) -> None:
        """
        Mark taint tags for source tools (post-execution)
        
        Uses summarized output to avoid performance issues with large objects.
        
        Args:
            state: Execution state
            services: Execution services
            output: Normalized StepOutput
        """
        if not services.taint_engine or not services.taint_store:
            return
        
        # Check if this is a source tool
        if not services.taint_store.is_source_tool(state.step.tool):
            return
        
        # Use summarized output (not full object) for taint marking
        # Get output value (may be large, but we only need it for pattern detection)
        output_value = output.value if hasattr(output, 'value') else output
        
        # Build context for on_call_success
        dlp_context = {
            "tool": state.step.tool,
            "params": state.step.params,
            "step_id": state.step.id,
            "run_id": state.ctx.run_id,
        }
        
        # Event emitter (optional, for audit)
        def emit_taint_event(event_data: Dict[str, Any]) -> None:
            """Emit taint event (for audit)"""
            pass  # Could record to trace if needed
        
        try:
            # Call DLP middleware on_call_success to mark taint tags
            services.taint_engine.on_call_success(
                tool_name=state.step.tool,
                params=state.step.params,
                context=dlp_context,
                result=output_value,  # Pass output for sensitivity inference
                emit=emit_taint_event,
            )
            
            # Store taint tags in state for trace/audit
            if services.taint_store.is_tainted(state.step.id):
                state.taint_tags = list(services.taint_store.get_tags(state.step.id))
        
        except Exception as e:
            # Don't fail execution if taint marking fails
            import logging
            logging.warning(
                f"Taint marking failed (non-fatal): {type(e).__name__}: {e}",
                exc_info=True,
            )
    
    def _register_spawned_pids(
        self,
        state: ExecutionState,
        services: ExecutionServices,
        tool_output: Any,
    ) -> None:
        """
        Register spawned PIDs in process registry for ownership tracking
        
        Args:
            state: Execution state
            services: Execution services
            tool_output: Tool output (may contain PID)
        
        Note:
            - Detects PROCESS_SPAWN operations (tool name contains 'spawn', 'start', 'popen')
            - Extracts PID from output or params
            - Registers PID in process registry for ownership checks
        """
        if not services.process_registry:
            return
        
        try:
            # Detect if this is a process spawn operation
            tool_name = state.step.tool.lower()
            is_spawn = any(keyword in tool_name for keyword in ['spawn', 'start', 'popen', 'launch', 'run'])
            
            if not is_spawn:
                return
            
            # Try to extract PID from output
            pid = None
            
            # Check if output is a dict with 'pid' key
            if isinstance(tool_output, dict) and 'pid' in tool_output:
                pid = tool_output['pid']
            # Check if output is an integer (direct PID return)
            elif isinstance(tool_output, int):
                pid = tool_output
            # Check if output has a 'pid' attribute (e.g., subprocess.Popen object)
            elif hasattr(tool_output, 'pid'):
                pid = tool_output.pid
            # Check params for PID (fallback)
            elif 'pid' in state.step.params:
                pid = state.step.params['pid']
            
            if pid is not None:
                # Convert to int if string
                try:
                    pid = int(pid)
                    services.process_registry.register_pid(pid)
                    
                    # Optionally record to trace
                    if hasattr(services.recorder, 'next_seq'):
                        from ...trace.events import EventType, TraceEvent, LogLevel, utc_now_iso
                        seq = services.recorder.next_seq()
                        event = TraceEvent(
                            schema="failcore.trace.v0.1.3",
                            seq=seq,
                            ts=utc_now_iso(),
                            level=LogLevel.INFO,
                            event={
                                "type": "PROCESS_REGISTERED",
                                "severity": "info",
                                "step": {
                                    "id": state.step.id,
                                    "tool": state.step.tool,
                                    "attempt": state.attempt,
                                },
                                "data": {
                                    "pid": pid,
                                    "message": f"Process {pid} registered as owned by this session",
                                },
                            },
                            run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
                        )
                        services.recorder.record(event)
                
                except (ValueError, TypeError):
                    # Invalid PID, skip registration
                    pass
        
        except Exception as e:
            # Don't fail execution if PID registration fails
            import logging
            logging.warning(
                f"PID registration failed (non-fatal): {type(e).__name__}: {e}",
                exc_info=True,
            )

    def _execute_with_timeout(
        self,
        fn: Any,
        params: dict,
        timeout: float,
        state: ExecutionState,
        services: ExecutionServices,
    ) -> Any:
        """
        Execute function with timeout enforcement
        
        阶段四：超时系统化
        - 使用 multiprocessing 或 threading + signal 实现超时
        - 超时后 kill 当前 step 的进程组（不是整个 session）
        - 记录 STEP_TIMEOUT 事件到 trace
        
        Args:
            fn: Tool function to execute
            params: Function parameters
            timeout: Timeout in seconds
            state: Execution state
            services: Execution services
            
        Returns:
            Function result
            
        Raises:
            TimeoutError: If execution exceeds timeout
        """
        import signal
        import sys
        import threading
        from failcore.core.types.step import StepStatus
        
        result_container = {"result": None, "error": None, "completed": False}
        
        def target():
            try:
                result_container["result"] = fn(**params)
                result_container["completed"] = True
            except Exception as e:
                result_container["error"] = e
                result_container["completed"] = False
        
        # Unix: Use signal.alarm for timeout (more reliable)
        if sys.platform != 'win32' and hasattr(signal, 'SIGALRM'):
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Step execution exceeded timeout of {timeout}s")
            
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout) + 1)  # +1 for safety
            
            try:
                result = fn(**params)
                signal.alarm(0)  # Cancel alarm
                return result
            except TimeoutError as e:
                # Timeout occurred - kill process group for this step
                self._handle_timeout(state, services, timeout)
                raise
            finally:
                signal.signal(signal.SIGALRM, old_handler)
        
        # Windows/fallback: Use threading
        else:
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            thread.join(timeout=timeout)
            
            if thread.is_alive():
                # Timeout occurred
                self._handle_timeout(state, services, timeout)
                raise TimeoutError(f"Step execution exceeded timeout of {timeout}s")
            
            if result_container["error"]:
                raise result_container["error"]
            
            if not result_container["completed"]:
                raise RuntimeError("Execution failed without setting result or error")
            
            return result_container["result"]
    
    def _handle_timeout(
        self,
        state: ExecutionState,
        services: ExecutionServices,
        timeout: float,
    ) -> None:
        """
        Handle step timeout - kill process group and record event
        
        步骤4：只 kill 当前执行域的进程组，不调用 cleanup()
        
        设计：
        - v1: 如果有 session-level PGID，kill 整个进程组
        - v2: 未来支持 per-step PGID，只 kill 当前 step 的进程组
        - 不调用 cleanup()（避免清理其他并发 step）
        
        Args:
            state: Execution state
            services: Execution services
            timeout: Timeout value that was exceeded
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.error(f"Step {state.step.id} ({state.step.tool}) exceeded timeout of {timeout}s")
        
        # 步骤4：kill 进程组（v1: session-level PGID）
        kill_success = False
        kill_error = None
        pgid = None
        
        if services.process_registry:
            try:
                pgid = services.process_registry.get_process_group()
                
                if pgid:
                    logger.info(f"Attempting to kill process group {pgid} due to timeout")
                    
                    from failcore.utils.process import kill_process_group
                    
                    # 只 kill 进程组，不调用 cleanup()
                    success, error = kill_process_group(
                        pgid=pgid,
                        timeout=5.0,
                        signal_escalation=True  # SIGTERM -> SIGKILL
                    )
                    
                    kill_success = success
                    kill_error = error
                    
                    if success:
                        logger.info(f"Successfully killed process group {pgid}")
                    else:
                        logger.error(f"Failed to kill process group {pgid}: {error}")
                else:
                    logger.warning("No process group ID available for timeout kill")
                    kill_error = "No PGID available"
            
            except Exception as e:
                kill_error = f"Unexpected error: {type(e).__name__}: {e}"
                logger.error(f"Error killing process group on timeout: {kill_error}", exc_info=True)
        else:
            logger.warning("Process registry not available for timeout kill")
            kill_error = "No process registry"
        
        # Record STEP_TIMEOUT event (步骤4要求：包含 kill 结果)
        if hasattr(services.recorder, 'next_seq'):
            from ...trace.events import EventType, TraceEvent, LogLevel, utc_now_iso
            from ...trace import ExecutionPhase
            
            seq = services.recorder.next_seq()
            event = TraceEvent(
                schema="failcore.trace.v0.1.3",
                seq=seq,
                ts=utc_now_iso(),
                level=LogLevel.ERROR,
                event={
                    "type": "STEP_TIMEOUT",
                    "severity": "error",
                    "step": {
                        "id": state.step.id,
                        "tool": state.step.tool,
                        "attempt": state.attempt,
                    },
                    "data": {
                        "timeout_seconds": timeout,  # 步骤1要求
                        "message": f"Step execution exceeded timeout of {timeout}s",
                        "phase": ExecutionPhase.EXECUTE.value,
                        # 步骤4要求：kill 结果
                        "process_group": {
                            "pgid": pgid,
                            "killed": kill_success,
                            "kill_error": kill_error,
                        },
                    },
                },
                run={"run_id": state.run_ctx["run_id"], "created_at": state.run_ctx["created_at"]},
            )
            
            try:
                services.recorder.record(event)
            except Exception as e:
                logger.warning(f"Failed to record STEP_TIMEOUT event: {e}")