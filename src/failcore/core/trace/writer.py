# failcore/core/trace/writer.py
"""
TraceWriter - unified event emission with automatic field population
"""

from __future__ import annotations
import threading
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .events import (
    TraceEvent,
    EventType,
    LogLevel,
    StepStatus,
    ExecutionPhase,
    utc_now_iso,
)
from .builder import (
    build_run_start_event,
    build_run_end_event,
    build_step_start_event,
    build_step_end_event,
    build_policy_denied_event,
    build_output_normalized_event,
    build_run_context,
    SCHEMA_VERSION,
    _get_host_info,
    _hash_value,
)
from .recorder import TraceRecorder


class TraceContext:
    """
    Trace context - maintains run state and sequence counter
    
    Thread-safe sequence generation and run context management.
    """
    
    def __init__(
        self,
        run_id: str,
        created_at: Optional[str] = None,
        workspace: Optional[str] = None,
        sandbox_root: Optional[str] = None,
        cwd: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        flags: Optional[Dict[str, Any]] = None,
    ):
        self.run_id = run_id
        self.created_at = created_at or utc_now_iso()
        self.workspace = workspace
        self.sandbox_root = sandbox_root
        self.cwd = cwd
        self.tags = tags or {}
        self.flags = flags or {}
        
        self._seq = 0
        self._lock = threading.Lock()
        
        # Build run context once
        self.run_context = build_run_context(
            run_id=self.run_id,
            created_at=self.created_at,
            workspace=self.workspace,
            sandbox_root=self.sandbox_root,
            cwd=self.cwd,
            tags=self.tags,
            flags=self.flags,
        )
    
    def next_seq(self) -> int:
        """Get next sequence number (thread-safe)"""
        with self._lock:
            self._seq += 1
            return self._seq
    
    def get_run_context(self) -> Dict[str, Any]:
        """Get run context dict"""
        return self.run_context


class TraceWriter:
    """
    TraceWriter - unified event emission interface
    
    Automatically fills: schema, run, seq, ts, level
    Ensures format consistency and prevents manual event construction.
    
    Example:
        >>> ctx = TraceContext(run_id="run_123", workspace=".failcore/runs/run_123")
        >>> writer = TraceWriter(ctx, recorder)
        >>> writer.run_start(tags={"env": "dev"})
        >>> writer.step_start(step_id="s0001", tool="fetch_data", params={"id": 123})
        >>> writer.policy_denied(step_id="s0001", tool="fetch_data", reason="Access denied")
        >>> writer.step_end(step_id="s0001", tool="fetch_data", status="BLOCKED", phase="policy", duration_ms=10)
        >>> writer.run_end(summary={"steps_total": 1, "blocked": 1})
    """
    
    def __init__(self, context: TraceContext, recorder: TraceRecorder):
        self.context = context
        self.recorder = recorder
        self._attempt_counter: Dict[str, int] = {}
    
    def emit(self, event: TraceEvent):
        """
        Emit a pre-built event
        
        For advanced usage when you need custom events.
        """
        self.recorder.record(event)
    
    def run_start(
        self,
        tags: Optional[Dict[str, str]] = None,
        flags: Optional[Dict[str, Any]] = None,
    ):
        """Emit RUN_START event"""
        # Update context if tags/flags provided
        if tags:
            self.context.tags.update(tags)
            self.context.run_context["tags"] = self.context.tags
        if flags:
            self.context.flags.update(flags)
            self.context.run_context["flags"] = self.context.flags
        
        event = build_run_start_event(
            seq=self.context.next_seq(),
            run_id=self.context.run_id,
            created_at=self.context.created_at,
            workspace=self.context.workspace,
            sandbox_root=self.context.sandbox_root,
            cwd=self.context.cwd,
            tags=self.context.tags,
            flags=self.context.flags,
        )
        self.recorder.record(event)
    
    def run_end(self, summary: Dict[str, Any]):
        """Emit RUN_END event"""
        event = build_run_end_event(
            seq=self.context.next_seq(),
            run_context=self.context.get_run_context(),
            summary=summary,
        )
        self.recorder.record(event)
    
    def step_start(
        self,
        step_id: str,
        tool: str,
        params: Dict[str, Any],
        depends_on: Optional[list] = None,
    ):
        """Emit STEP_START event"""
        # Track attempt
        attempt = self._attempt_counter.get(step_id, 0) + 1
        self._attempt_counter[step_id] = attempt
        
        event = build_step_start_event(
            seq=self.context.next_seq(),
            run_context=self.context.get_run_context(),
            step_id=step_id,
            tool=tool,
            params=params,
            attempt=attempt,
            depends_on=depends_on,
        )
        self.recorder.record(event)
    
    def step_end(
        self,
        step_id: str,
        tool: str,
        status: str,
        phase: str,
        duration_ms: int,
        output: Optional[Any] = None,
        error: Optional[Dict[str, Any]] = None,
        warnings: Optional[list] = None,
    ):
        """Emit STEP_END event"""
        attempt = self._attempt_counter.get(step_id, 1)
        
        # Convert string to enum
        status_enum = StepStatus(status) if isinstance(status, str) else status
        phase_enum = ExecutionPhase(phase) if isinstance(phase, str) else phase
        
        event = build_step_end_event(
            seq=self.context.next_seq(),
            run_context=self.context.get_run_context(),
            step_id=step_id,
            tool=tool,
            attempt=attempt,
            status=status_enum,
            phase=phase_enum,
            duration_ms=duration_ms,
            output=output,
            error=error,
            warnings=warnings,
        )
        self.recorder.record(event)
    
    def policy_denied(
        self,
        step_id: str,
        tool: str,
        policy_id: str,
        rule_id: str,
        rule_name: str,
        reason: str,
    ):
        """Emit POLICY_DENIED event"""
        attempt = self._attempt_counter.get(step_id, 1)
        
        event = build_policy_denied_event(
            seq=self.context.next_seq(),
            run_context=self.context.get_run_context(),
            step_id=step_id,
            tool=tool,
            attempt=attempt,
            policy_id=policy_id,
            rule_id=rule_id,
            rule_name=rule_name,
            reason=reason,
        )
        self.recorder.record(event)
    
    def output_normalized(
        self,
        step_id: str,
        tool: str,
        expected_kind: Optional[str],
        observed_kind: str,
        reason: Optional[str] = None,
    ):
        """Emit OUTPUT_NORMALIZED event"""
        attempt = self._attempt_counter.get(step_id, 1)
        
        event = build_output_normalized_event(
            seq=self.context.next_seq(),
            run_context=self.context.get_run_context(),
            step_id=step_id,
            tool=tool,
            attempt=attempt,
            expected_kind=expected_kind,
            observed_kind=observed_kind,
            reason=reason,
        )
        self.recorder.record(event)
    
    def validation_failed(
        self,
        step_id: str,
        tool: str,
        kind: str,
        check_id: str,
        reason: str,
        field: Optional[str] = None,
    ):
        """Emit VALIDATION_FAILED event"""
        attempt = self._attempt_counter.get(step_id, 1)
        
        event = TraceEvent(
            schema=SCHEMA_VERSION,
            seq=self.context.next_seq(),
            ts=utc_now_iso(),
            level=LogLevel.WARN,
            event={
                "type": EventType.VALIDATION_FAILED.value,
                "step": {"id": step_id, "tool": tool, "attempt": attempt},
                "data": {
                    "validation": {
                        "kind": kind,
                        "check_id": check_id,
                        "decision": "deny",
                        "reason": reason,
                        "field": field,
                    }
                },
            },
            run={"run_id": self.context.run_id, "created_at": self.context.created_at},
        )
        self.recorder.record(event)
