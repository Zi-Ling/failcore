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
    """Trace event types following v0.1.1 spec"""
    # Run lifecycle
    RUN_START = "RUN_START"
    RUN_END = "RUN_END"
    
    # Step lifecycle
    STEP_START = "STEP_START"
    STEP_END = "STEP_END"
    
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


class StepStatus(str, Enum):
    """Step execution status"""
    OK = "OK"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    REPLAYED = "REPLAYED"


class ExecutionPhase(str, Enum):
    """Execution phases"""
    VALIDATE = "validate"
    POLICY = "policy"
    EXECUTE = "execute"
    COMMIT = "commit"
    REPLAY = "replay"
    NORMALIZE = "normalize"


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
    """Step information"""
    id: str
    tool: str
    attempt: int = 1
    depends_on: List[str] = field(default_factory=list)
    fingerprint: Optional[Dict[str, Any]] = None
    contract: Optional[Dict[str, Any]] = None


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
    """Step execution result"""
    status: StepStatus
    phase: ExecutionPhase
    duration_ms: int
    error: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class PolicyInfo:
    """Policy decision information"""
    policy_id: str
    rule_id: str
    rule_name: str
    decision: str  # allow | deny
    reason: str
    action_taken: str  # continue | halt
    matched_rules: List[str] = field(default_factory=list)


@dataclass
class ValidationInfo:
    """Validation check information"""
    kind: str  # precondition | schema | invariant
    check_id: str
    decision: str  # pass | deny
    reason: str
    field: Optional[str] = None


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
