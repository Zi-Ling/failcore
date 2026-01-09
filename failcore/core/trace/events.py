# failcore/core/trace/events.py
"""
Trace event models following failcore.trace.v0.1.1 specification
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Get current UTC time in ISO8601 format"""
    return datetime.now(timezone.utc).isoformat()


# Event Types
class EventType(str, Enum):
    """Trace event types following v0.1.3 schemas"""
    # Run lifecycle
    RUN_START = "RUN_START"
    RUN_END = "RUN_END"
    
    # Business action lifecycle (unified for SDK + Proxy)
    ATTEMPT = "ATTEMPT"
    RESULT = "RESULT"
    
    # Execution gateway events
    FINGERPRINT_COMPUTED = "FINGERPRINT_COMPUTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    POLICY_DENIED = "POLICY_DENIED"
    OUTPUT_NORMALIZED = "OUTPUT_NORMALIZED"
    ARTIFACT_WRITTEN = "ARTIFACT_WRITTEN"
    SIDE_EFFECT_APPLIED = "SIDE_EFFECT_APPLIED"
    
    # Replay events
    REPLAY_STEP_HIT = "REPLAY_STEP_HIT"
    REPLAY_STEP_MISS = "REPLAY_STEP_MISS"
    REPLAY_POLICY_DIFF = "REPLAY_POLICY_DIFF"
    REPLAY_OUTPUT_DIFF = "REPLAY_OUTPUT_DIFF"
    REPLAY_INJECTED = "REPLAY_INJECTED"


class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


# Trace-specific step status (event-level semantics)
# Separated from execution-level StepStatus to maintain clear boundaries
class TraceStepStatus(str, Enum):
    """
    Trace event step status (event-level semantics)
    
    This enum represents the status of a step as recorded in trace events.
    It extends execution-level StepStatus with trace-specific states like
    REPLAYED and SKIPPED, which are event-level observations rather than
    execution results.
    
    Design principle:
    - Execution status (StepStatus): ok/fail/blocked (execution result)
    - Event status (TraceStepStatus): ok/fail/blocked/skipped/replayed (trace observation)
    - Use map_step_status_to_trace() to convert StepStatus → TraceStepStatus
    """
    OK = "ok"
    FAIL = "fail"
    BLOCKED = "blocked"
    SKIPPED = "skipped"  # Event-level: step was skipped in trace
    REPLAYED = "replayed"  # Event-level: step was replayed from history


class ExecutionPhase(str, Enum):
    """
    Execution phases (standardized)
    
    These phases represent the canonical execution pipeline:
    - VALIDATE: Pre-execution validation (type check, preconditions)
    - POLICY: Policy decision (allow/deny/warn)
    - EXECUTE: Actual tool execution
    - COMMIT: Post-execution commit (side effects, artifacts)
    - REPLAY: Replay mode execution
    - NORMALIZE: Output normalization
    """
    VALIDATE = "validate"
    POLICY = "policy"
    EXECUTE = "execute"
    COMMIT = "commit"
    REPLAY = "replay"
    NORMALIZE = "normalize"


class EventSeverity(str, Enum):
    """
    Event severity level (REQUIRED for all events)
    
    - INFO: Informational event (normal operation)
    - WARN: Warning (potential issue, but operation continues)
    - ERROR: Error (operation failed or blocked)
    - CRITICAL: Critical error (system integrity issue)
    """
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StepProvenance(str, Enum):
    """
    Step provenance (REQUIRED for all steps)
    
    Tracks where the step execution came from:
    - LIVE: Fresh execution
    - REPLAY_HIT: Replayed from historical trace (fingerprint match)
    - REPLAY_MISS: Fingerprint miss, executed live
    - INJECTED: Manually injected step
    - MOCK: Mocked execution
    """
    LIVE = "LIVE"
    REPLAY_HIT = "REPLAY_HIT"
    REPLAY_MISS = "REPLAY_MISS"
    INJECTED = "INJECTED"
    MOCK = "MOCK"


class ErrorCode(str, Enum):
    """
    Standardized error codes 
    
    File system errors:
    - FILE_NOT_FOUND: File does not exist
    - PATH_TRAVERSAL: Path escapes sandbox boundary
    - PATH_INVALID: Invalid path format
    - PERMISSION_DENIED: Permission denied
    
    Network errors:
    - SSRF_BLOCKED: SSRF attack blocked
    - DOMAIN_NOT_ALLOWED: Domain not in allowlist
    - PORT_NOT_ALLOWED: Port not allowed
    - UNSAFE_PROTOCOL: Unsafe protocol
    
    Validation errors:
    - PARAM_TYPE_MISMATCH: Parameter type mismatch
    - PARAM_MISSING: Required parameter missing
    - PARAM_INVALID: Invalid parameter value
    - CONTRACT_VIOLATION: Output contract violation
    - CONTRACT_DRIFT: Output contract drift
    
    Policy errors:
    - POLICY_DENIED: Policy denied execution
    - POLICY_BLOCKED: Policy blocked execution
    
    Execution errors:
    - EXECUTION_FAILED: Tool execution failed
    - EXECUTION_TIMEOUT: Execution timeout
    """
    # File system
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PATH_TRAVERSAL = "PATH_TRAVERSAL"  # ../escape attempts
    SANDBOX_VIOLATION = "SANDBOX_VIOLATION"  # Absolute path outside sandbox
    PATH_INVALID = "PATH_INVALID"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    
    # Network
    SSRF_BLOCKED = "SSRF_BLOCKED"
    DOMAIN_NOT_ALLOWED = "DOMAIN_NOT_ALLOWED"
    PORT_NOT_ALLOWED = "PORT_NOT_ALLOWED"
    UNSAFE_PROTOCOL = "UNSAFE_PROTOCOL"
    
    # Validation
    PARAM_TYPE_MISMATCH = "PARAM_TYPE_MISMATCH"
    PARAM_MISSING = "PARAM_MISSING"
    PARAM_INVALID = "PARAM_INVALID"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    CONTRACT_DRIFT = "CONTRACT_DRIFT"
    
    # Policy
    POLICY_DENIED = "POLICY_DENIED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    
    # Execution
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    
    # Generic
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# Data models
@dataclass
class RunContext:
    """Run context information"""
    run_id: str
    created_at: str
    workspace: Optional[str] = None
    sandbox_root: Optional[str] = None
    cwd: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)
    version: Dict[str, str] = field(default_factory=dict)


@dataclass
class StepInfo:
    """
    Step information (enhanced with required fields)
    """
    id: str
    tool: str
    provenance: StepProvenance  # REQUIRED: step provenance
    attempt: int = 1
    depends_on: List[str] = field(default_factory=list)
    fingerprint: Optional[Dict[str, Any]] = None
    contract: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # Tool metadata


@dataclass
class PayloadInfo:
    """Input/Output payload information"""
    mode: str = "summary"  # none | summary | full | ref
    schema: Optional[str] = None
    summary: Optional[Any] = None
    hash: Optional[str] = None
    redaction: Optional[Dict[str, Any]] = None
    kind: Optional[str] = None  # For output: text | json | artifacts | bytes


@dataclass
class ResultInfo:
    """
    Step execution result (enhanced with required fields)
    """
    status: TraceStepStatus  # Use TraceStepStatus for trace events
    phase: ExecutionPhase  # REQUIRED: execution phase
    duration_ms: int
    severity: EventSeverity  # REQUIRED: event severity
    error: Optional[Dict[str, Any]] = None  # Must include 'code' if present
    warnings: List[str] = field(default_factory=list)


@dataclass
class PolicyInfo:
    """
    Policy decision information (enhanced with severity)
    """
    policy_id: str
    rule_id: str
    rule_name: str
    decision: str  # allow | deny | warn
    reason: str
    action_taken: str  # continue | halt | warn
    severity: EventSeverity  # REQUIRED
    code: Optional[str] = None  # ErrorCode if denied
    matched_rules: List[str] = field(default_factory=list)


@dataclass
class ValidationInfo:
    """
    Validation check information (enhanced with error codes)
    """
    kind: str  # precondition | schema | invariant | postcondition
    check_id: str
    decision: str  # pass | deny | warn
    reason: str
    code: Optional[str] = None  # ErrorCode if failed
    field: Optional[str] = None
    severity: EventSeverity = EventSeverity.INFO  # REQUIRED


@dataclass
class NormalizeInfo:
    """Output normalization information"""
    expected_kind: Optional[str] = None
    observed_kind: Optional[str] = None
    decision: str = "ok"  # ok | mismatch
    reason: Optional[str] = None
    strategy: Optional[str] = None


@dataclass
class ArtifactInfo:
    """Artifact reference"""
    uri: str
    name: str
    kind: str = "file"
    media_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None


@dataclass
class ReplayInfo:
    """Replay execution information"""
    mode: str  # report | mock | resume
    hit_type: str  # HIT | MISS | DIFF
    fingerprint_id: Optional[str] = None
    matched_step_id: Optional[str] = None
    source_trace: Optional[str] = None
    injected: bool = False
    diff_type: Optional[str] = None  # policy | output | normalize
    historical_value: Optional[Any] = None
    current_value: Optional[Any] = None
    reason: Optional[str] = None


@dataclass
class SideEffectInfo:
    """
    Side-effect information
    
    Records what side-effect occurred during execution.
    This is a fact-only record - no judgment, no blocking, just observation.
    """
    type: str  # Side-effect type (e.g., "filesystem.write", "network.egress")
    target: Optional[str] = None  # Target of the side-effect (e.g., "/etc/passwd", "api.example.com")
    category: Optional[str] = None  # Side-effect category (e.g., "filesystem", "network")
    tool: Optional[str] = None  # Tool that caused the side-effect
    step_id: Optional[str] = None  # Step ID where side-effect occurred
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata


@dataclass
class TraceEvent:
    """
    Trace event following failcore.trace.v0.1.1 specification
    
    Top-level required fields:
    - schema: version identifier
    - seq: monotonic sequence number within run
    - ts: ISO8601 timestamp
    - level: log level
    - event: event body
    - run: run context
    """
    # Top-level required
    schema: str
    seq: int
    ts: str
    level: LogLevel
    event: Dict[str, Any]
    run: Dict[str, Any]
    
    # Recommended
    host: Optional[Dict[str, Any]] = None
    actor: Optional[Dict[str, Any]] = None
    trace: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "schema": self.schema,
            "seq": self.seq,
            "ts": self.ts,
            "level": self.level.value if isinstance(self.level, Enum) else self.level,
            "event": self.event,
            "run": self.run,
        }
        
        if self.host:
            result["host"] = self.host
        if self.actor:
            result["actor"] = self.actor
        if self.trace:
            result["trace"] = self.trace
        if self.security:
            result["security"] = self.security
        
        return result
