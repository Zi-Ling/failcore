from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional, Literal, Union


# =========================
# JSON-serializable values
# =========================

JSONPrimitive = Union[str, int, float, bool, None]
JSONValue = Union[
    JSONPrimitive,
    Dict[str, Any],
    List[Any],
]
# NOTE:
# JSONValue is intentionally permissive.
# Runtime / middleware should ensure values are JSON-serializable
# (no bytes, file handles, sockets, complex objects, etc.).


# =========================
# Runtime Call Context
# =========================

@dataclass
class CallContext:
    """
    Runtime context for a single tool invocation.

    Treat this object as immutable after creation.

    Rules:
    - Do NOT mutate metadata in-place.
    - Use with_metadata() to derive a new context.
    """

    # Execution identity
    run_id: str
    trace_id: str

    # Wall-clock start time (epoch seconds)
    # Used for latency computation and audit timeline
    start_time: float = field(default_factory=time.time)

    # Replay / determinism anchors
    replay_id: Optional[str] = None
    deterministic_seed: Optional[str] = None

    # Cross-cutting metadata (tenant, env, user, quota, etc.)
    # Exposed as Mapping to discourage mutation
    metadata: Mapping[str, str] = field(default_factory=dict)

    def with_metadata(self, **updates: str) -> "CallContext":
        """
        Return a new CallContext with merged metadata.

        This preserves immutability semantics while allowing
        controlled context extension.
        """
        merged = dict(self.metadata)
        merged.update(updates)
        return replace(self, metadata=merged)


# =========================
# Execution Receipt
# =========================

ReceiptKind = Literal[
    "file",      # filesystem side effects
    "network",   # outbound/inbound network access
    "process",   # subprocess / command execution
    "resource",  # cpu/memory/disk usage summary
    "custom",    # extension point
]


@dataclass(frozen=True)
class Receipt:
    """
    Structured summary of a side effect caused by tool execution.

    Receipts are used for:
    - audit trail
    - forensic / root-cause analysis
    - replay & dry-run validation

    Keep Receipt.data JSON-serializable.
    """

    kind: ReceiptKind
    data: Dict[str, Any]


# =========================
# Tool Invocation Result
# =========================

@dataclass
class ToolResult:
    """
    Normalized result returned by ToolRuntime.call().

    Semantics:
    - content: agent-visible output (JSON-serializable)
    - raw: transport raw output (audit/debug ONLY)
    """

    ok: bool

    # Agent-visible output
    content: Optional[JSONValue] = None

    # Raw transport output (do NOT expose to agent)
    raw: Any = None

    # Normalized error payload (if ok == False)
    error: Optional[Dict[str, Any]] = None

    # Optional execution metadata (tokens, cost, duration, etc.)
    usage: Optional[Dict[str, Any]] = None

    # Structured side-effect receipts
    receipts: List[Receipt] = field(default_factory=list)


# =========================
# Runtime Event (Streaming)
# =========================

ToolEventType = Literal[
    "start",
    "progress",
    "log",
    "partial",
    "result",
    "error",
]


@dataclass
class ToolEvent:
    """
    Streaming event emitted during tool execution.

    Ordering:
    - seq is assigned by the runtime (monotonic).

    Timing:
    - timestamp is wall-clock emission time (epoch seconds).

    These guarantees allow deterministic reconstruction
    for audit, replay, and incident analysis.
    """

    # Monotonic sequence number (assigned by runtime)
    seq: int

    # Wall-clock time at emission
    timestamp: float = field(default_factory=time.time)

    type: ToolEventType
    message: Optional[str] = None

    # Flexible payload (can be refined later per event type)
    data: Optional[Any] = None

    # Execution identity for correlation
    trace_id: Optional[str] = None
    run_id: Optional[str] = None


# =========================
# Tool Spec Reference
# =========================

@dataclass(frozen=True)
class ToolSpecRef:
    """
    Lightweight reference to a canonical ToolSpec.

    This does NOT redefine tool schema or spec.
    It only points to the authoritative definition
    under core/tools/spec.py.

    Frozen to support use as dict keys / set members
    in runtime registries and caches.
    """

    name: str
    provider: Optional[str] = None
    version: Optional[str] = None
