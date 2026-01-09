# failcore/core/trace/writer.py
"""
TraceWriter - unified event emission with automatic field population

EventWriter - low-level unified trace writer that enforces v0.1.3 envelope format
"""

from __future__ import annotations
import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone
from dataclasses import is_dataclass, asdict

from .events import (
    TraceEvent,
    EventType,
    LogLevel,
    TraceStepStatus,  # Use TraceStepStatus for trace events
    ExecutionPhase,
    utc_now_iso,
)
from .builder import (
    build_run_start_event,
    build_run_end_event,
    build_attempt_event,
    build_result_event,
    build_policy_denied_event,
    build_output_normalized_event,
    build_run_context,
    SCHEMA_VERSION,
    _get_host_info,
    _hash_value,
)
from .recorder import TraceRecorder, _default_json_encoder


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
        >>> writer.attempt(step_id="s0001", tool="fetch_data", params={"id": 123})
        >>> writer.policy_denied(step_id="s0001", tool="fetch_data", reason="Access denied")
        >>> writer.result(step_id="s0001", tool="fetch_data", status="blocked", phase="policy", duration_ms=10)
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
    
    def attempt(
        self,
        step_id: str,
        tool: str,
        params: Dict[str, Any],
        depends_on: Optional[list] = None,
    ):
        """Emit ATTEMPT event (business action start)"""
        # Track attempt
        attempt = self._attempt_counter.get(step_id, 0) + 1
        self._attempt_counter[step_id] = attempt
        
        event = build_attempt_event(
            seq=self.context.next_seq(),
            run_context=self.context.get_run_context(),
            step_id=step_id,
            tool=tool,
            params=params,
            attempt=attempt,
            depends_on=depends_on,
        )
        self.recorder.record(event)
    
    def result(
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
        """Emit RESULT event (business action end)"""
        attempt = self._attempt_counter.get(step_id, 1)
        
        # Convert string to enum (use TraceStepStatus for trace events)
        from .events import TraceStepStatus
        status_enum = TraceStepStatus(status) if isinstance(status, str) else status
        phase_enum = ExecutionPhase(phase) if isinstance(phase, str) else phase
        
        event = build_result_event(
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


class EventWriter:
    """
    Low-level unified event writer - single authoritative write entry point
    
    Enforces v0.1.3 envelope format for all events:
    {
        "schema": "failcore.trace.v0.1.3",
        "seq": N,
        "ts": "2026-01-09T...",
        "level": "INFO",
        "event": {...},
        "run": {...}
    }
    
    Key design principles:
    - No module may "self-write" trace format anymore
    - All writes go through EventWriter.write(...)
    - Automatically manages seq counter, timestamps, run context
    - Fail-open: write failures logged but never raise
    - Thread-safe for concurrent writes
    
    Usage:
        # For proxy/CLI:
        writer = EventWriter(trace_path, run_id="run_123", kind="proxy")
        writer.write_run_event("RUN_START", {"mode": "warn", "listen": "127.0.0.1:8000"})
        writer.write_egress_event(egress_event)
        writer.write_run_event("RUN_END", {})
        writer.close()
        
        # For EgressEngine (via TraceSink wrapper):
        writer = EventWriter(trace_path, run_id="run_123", kind="run")
        writer.write_egress_event(egress_event)
    """
    
    def __init__(
        self,
        trace_path: Union[str, Path],
        *,
        run_id: str,
        kind: str = "run",  # "run", "proxy", "mcp"
        buffer_size: int = 1,  # Lines to buffer before flush
        flush_interval_s: float = 0.0,  # Auto-flush interval (0 = sync mode)
        **run_metadata: Any,  # Additional run metadata (workspace, sandbox_root, etc.)
    ):
        """
        Initialize EventWriter
        
        Args:
            trace_path: Path to trace.jsonl file
            run_id: Run identifier
            kind: Run kind ("run", "proxy", "mcp")
            buffer_size: Number of events to buffer (1 = sync)
            flush_interval_s: Auto-flush interval (0 = disabled)
            **run_metadata: Additional metadata for run context
        """
        self.trace_path = Path(trace_path)
        self.run_id = run_id
        self.kind = kind
        self.run_metadata = run_metadata
        
        # Ensure parent directory exists
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file in append mode
        self._file = open(self.trace_path, 'a', encoding='utf-8', buffering=1 if buffer_size == 1 else -1)
        
        # Sequence counter (thread-safe)
        self._seq = 0
        self._lock = threading.Lock()
        
        # Buffer management
        self._buffer: list[str] = []
        self._buffer_size = buffer_size
        self._flush_interval_s = flush_interval_s
        self._last_flush = datetime.now(timezone.utc).timestamp()
        
        # Build base run context (shared by all events)
        self._run_context = {
            "run_id": self.run_id,
            "kind": self.kind,
            **self.run_metadata,
        }
    
    def _next_seq(self) -> int:
        """Get next sequence number (thread-safe)"""
        with self._lock:
            self._seq += 1
            return self._seq
    
    def write(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        *,
        level: str = "INFO",
        run_override: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Write arbitrary event in v0.1.3 envelope format
        
        Args:
            event_type: Event type (RUN_START, EGRESS_EVENT, etc.)
            event_data: Event-specific data
            level: Log level (DEBUG, INFO, WARN, ERROR)
            run_override: Override run context for this event
        """
        try:
            envelope = {
                "schema": SCHEMA_VERSION,
                "seq": self._next_seq(),
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "event": {
                    "type": event_type,
                    **event_data,
                },
                "run": run_override or self._run_context,
            }
            
            # Serialize to JSON
            line = json.dumps(envelope, default=_default_json_encoder) + '\n'
            
            # Buffer or write immediately
            with self._lock:
                if self._buffer_size <= 1:
                    # Sync mode: write immediately
                    self._file.write(line)
                    self._file.flush()
                else:
                    # Buffered mode
                    self._buffer.append(line)
                    if len(self._buffer) >= self._buffer_size:
                        self._flush_buffer()
                    elif self._flush_interval_s > 0:
                        now = datetime.now(timezone.utc).timestamp()
                        if now - self._last_flush >= self._flush_interval_s:
                            self._flush_buffer()
        
        except Exception as e:
            # Fail-open: log error but don't raise
            import sys
            print(f"EventWriter: Failed to write event: {e}", file=sys.stderr)
    
    def write_run_event(self, event_type: str, run_data: Dict[str, Any]) -> None:
        """
        Write RUN_START or RUN_END event
        
        Args:
            event_type: "RUN_START" or "RUN_END"
            run_data: Run-specific data (mode, listen, summary, etc.)
        """
        self.write(
            event_type=event_type,
            event_data={"severity": "ok"},
            level="INFO",
            run_override={**self._run_context, **run_data},
        )
    
    def write_egress_event(self, egress_event: Any) -> None:
        """
        Write EGRESS_EVENT from EgressEvent object
        
        Args:
            egress_event: EgressEvent instance or dict
        """
        # Convert EgressEvent to dict if needed
        if hasattr(egress_event, 'to_dict'):
            event_dict = egress_event.to_dict()
        elif isinstance(egress_event, dict):
            event_dict = egress_event
        else:
            raise ValueError(f"Invalid egress_event type: {type(egress_event)}")
        
        # Clean up event dict: remove redundant/null fields
        cleaned_data = self._clean_egress_data(event_dict)
        
        # Extract core fields for envelope
        event_data = {
            "severity": "ok",  # Egress events are informational
            "data": cleaned_data,  # Wrap cleaned fields in data
        }
        
        self.write(
            event_type="EGRESS_EVENT",
            event_data=event_data,
            level="INFO",
        )
    
    def _clean_egress_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean egress data before writing to trace
        
        Optimizations:
        1. Remove redundant run_id (already in envelope.run)
        2. Remove redundant timestamp (already in envelope.ts)
        3. Remove null/empty fields (summary, error, etc.)
        4. Clean response_headers (remove null values)
        5. Normalize JSON strings in request_body/body_preview
        6. Limit tool_output size (controllable via env var)
        7. Standardize usage fields (keep only canonical names)
        """
        import os
        
        cleaned = {}
        evidence = data.get('evidence', {})
        
        for key, value in data.items():
            # Skip redundant run-level fields (already in envelope.run)
            if key in ('run_id', 'timestamp'):
                continue
            
            # Skip null/None fields
            if value is None:
                continue
            
            # Process evidence dict
            if key == 'evidence' and isinstance(value, dict):
                value = self._clean_evidence(value)
            
            cleaned[key] = value
        
        return cleaned
    
    def _clean_evidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Clean evidence fields"""
        import os
        import json
        
        cleaned = {}
        
        # Check if full body capture is enabled
        capture_full_body = os.getenv('FAILCORE_TRACE_CAPTURE_BODY', '0') == '1'
        
        for key, value in evidence.items():
            # Skip null/None fields
            if value is None:
                continue
            
            # Clean response_headers: remove null values
            if key == 'response_headers' and isinstance(value, dict):
                value = {k: v for k, v in value.items() if v is not None}
                if not value:  # Skip if empty after cleaning
                    continue
            
            # Normalize JSON strings (request_body, body_preview)
            if key in ('request_body', 'body_preview') and isinstance(value, str):
                try:
                    # Parse and re-serialize with consistent format
                    obj = json.loads(value)
                    value = json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
                except (json.JSONDecodeError, ValueError):
                    pass  # Keep as-is if not valid JSON
            
            # Limit tool_output unless full capture is enabled
            if key == 'tool_output' and not capture_full_body:
                # Skip tool_output by default (we already have body_sha256/body_preview/usage)
                # Only include if explicitly requested via FAILCORE_TRACE_CAPTURE_BODY=1
                continue
            
            # Clean usage: keep only canonical OpenAI names
            if key == 'usage' and isinstance(value, dict):
                value = self._clean_usage_fields(value)
            
            cleaned[key] = value
        
        return cleaned
    
    def _clean_usage_fields(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize usage fields to canonical OpenAI naming
        
        Keep only: prompt_tokens, completion_tokens, total_tokens, cost_usd, estimated
        Remove: input_tokens, output_tokens (aliases)
        """
        canonical = {}
        
        # Canonical fields (OpenAI standard)
        for field in ('prompt_tokens', 'completion_tokens', 'total_tokens', 
                      'cost_usd', 'estimated', 'source', 'model', 'provider', 'api_calls'):
            if field in usage and usage[field] is not None:
                canonical[field] = usage[field]
        
        return canonical
    
    def attempt(
        self,
        step_id: str,
        tool: str,
        *,
        method: Optional[str] = None,
        endpoint: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        fingerprint_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Write ATTEMPT event (business action start)
        
        Used by both SDK (tool calls) and Proxy (HTTP requests).
        
        Args:
            step_id: Unique step/request ID
            tool: Tool name (SDK) or proxy:<endpoint> (Proxy)
            method: HTTP method (Proxy only)
            endpoint: HTTP endpoint (Proxy only)
            params: Tool parameters (SDK only)
            fingerprint_hash: Fingerprint for replay matching
            metadata: Additional metadata
        """
        step_data = {
            "id": step_id,
            "tool": tool,
            "attempt": 1,
        }
        
        # Add fingerprint if provided
        if fingerprint_hash:
            step_data["fingerprint"] = {
                "hash": fingerprint_hash,
                "version": 1,
                "components": ["method", "endpoint"] if method else ["tool", "params"],
            }
        
        # Build data payload
        data = {}
        if method:
            data["method"] = method
        if endpoint:
            data["endpoint"] = endpoint
        if params:
            data["params"] = params
        if metadata:
            data.update(metadata)
        
        self.write(
            event_type="ATTEMPT",
            event_data={
                "severity": "ok",
                "step": step_data,
                "data": data if data else {},
            },
            level="INFO",
        )
    
    def result(
        self,
        step_id: str,
        *,
        status: str = "OK",
        duration_ms: Optional[float] = None,
        output: Optional[Any] = None,
        error: Optional[Dict[str, Any]] = None,
        http_status: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Write RESULT event (business action end)
        
        Used by both SDK and Proxy.
        
        Args:
            step_id: Unique step/request ID (must match ATTEMPT)
            status: Result status (OK, ERROR, BLOCKED)
            duration_ms: Execution duration
            output: Tool output (SDK)
            error: Error details if failed
            http_status: HTTP status code (Proxy)
            metadata: Additional metadata
        """
        step_data = {"id": step_id}
        
        # Build result payload
        result_data = {"status": status}
        if duration_ms is not None:
            result_data["duration_ms"] = duration_ms
        if http_status is not None:
            result_data["http_status"] = http_status
        if output is not None:
            result_data["output"] = output
        if error is not None:
            result_data["error"] = error
        
        # Build data payload
        data = {"result": result_data}
        if metadata:
            data.update(metadata)
        
        self.write(
            event_type="RESULT",
            event_data={
                "severity": "ok" if status == "OK" else "warn",
                "step": step_data,
                "data": data,
            },
            level="INFO" if status == "OK" else "WARN",
        )
    
    def write_trace_event(self, trace_event: TraceEvent) -> None:
        """
        Write TraceEvent (from SDK/run mode)
        
        Args:
            trace_event: TraceEvent instance
        """
        # TraceEvent already has envelope structure
        event_dict = trace_event.to_dict()
        
        # Write directly (already in v0.1.3 format)
        try:
            line = json.dumps(event_dict, default=_default_json_encoder) + '\n'
            
            with self._lock:
                if self._buffer_size <= 1:
                    self._file.write(line)
                    self._file.flush()
                else:
                    self._buffer.append(line)
                    if len(self._buffer) >= self._buffer_size:
                        self._flush_buffer()
        
        except Exception as e:
            import sys
            print(f"EventWriter: Failed to write TraceEvent: {e}", file=sys.stderr)
    
    def _flush_buffer(self) -> None:
        """Flush buffered events (must hold lock)"""
        if not self._buffer:
            return
        
        try:
            self._file.writelines(self._buffer)
            self._file.flush()
            self._buffer.clear()
            self._last_flush = datetime.now(timezone.utc).timestamp()
        except Exception as e:
            import sys
            print(f"EventWriter: Failed to flush buffer: {e}", file=sys.stderr)
    
    def flush(self) -> None:
        """Flush buffered events to disk"""
        with self._lock:
            self._flush_buffer()
    
    def close(self) -> None:
        """Close writer and flush remaining events"""
        try:
            self.flush()
            self._file.close()
        except Exception as e:
            import sys
            print(f"EventWriter: Failed to close: {e}", file=sys.stderr)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
