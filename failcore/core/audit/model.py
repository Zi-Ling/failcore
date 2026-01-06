# failcore/core/audit/model.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import hashlib
import os
import platform
import re
import socket
import uuid


AUDIT_SCHEMA_V0_1_0 = "failcore.audit.v0.1.0"

# JSON-safe primitive types (keep v0.1 simple and serializable)
JsonPrimitive = Union[str, int, float, bool, None]
JsonMeta = Dict[str, JsonPrimitive]


def utc_now_iso() -> str:
    # audit: always explicit UTC with Z suffix; avoid microsecond noise.
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def new_report_id() -> str:
    return str(uuid.uuid4())


def sanitize_hostname(hostname: str, *, limit: int = 64) -> str:
    """
    Sanitize hostname for display / bundle filenames.
    - strip risky path characters
    - collapse whitespace
    - truncate for k8s pod-name length explosion
    """
    h = hostname.strip()
    h = re.sub(r"\s+", "-", h)
    # replace path-ish characters and other separators
    h = re.sub(r"[\\/:\*\?\"<>\|\x00-\x1f]", "-", h)
    # keep it readable
    h = re.sub(r"-{2,}", "-", h).strip("-")
    if not h:
        h = "host"
    if len(h) > limit:
        h = h[:limit]
    return h


def new_run_id(prefix: str = "run") -> str:
    """
    Generate a run_id that is:
    - unique enough for single-host runs
    - readable in audit bundles
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = sanitize_hostname(socket.gethostname() or "host")
    pid = os.getpid()
    rid = uuid.uuid4().hex[:8]
    return f"{prefix}-{ts}-{host}-{pid}-{rid}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def normalize_metadata(meta: Dict[str, Any]) -> JsonMeta:
    """
    Normalize metadata into JSON-safe primitives to avoid serialization surprises.

    v0.1 policy:
    - keep only primitives (str/int/float/bool/None)
    - everything else -> str(value)
    """
    out: JsonMeta = {}
    for k, v in (meta or {}).items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[str(k)] = v
        else:
            out[str(k)] = truncate(str(v), 512)
    return out


@dataclass(frozen=True)
class IntegrityPlaceholder:
    """
    Integrity placeholder for future signing / attestation.

    v0.1 contract:
      - attestation is always None
      - hashes may be used by infra/bundle layer
    """
    attestation: Optional[str] = None  # reserved for KMS/HSM signatures in future versions


@dataclass(frozen=True)
class TriggeredBy:
    """
    Best-effort cause-effect chain.

    Example:
      policy_denied caused_by tool_call (event_seq=12) which used args derived from prompt fragment.
    """
    source_type: str  # "tool_call" | "prompt_fragment" | "memory_item" | "unknown"
    source_event_seq: Optional[int] = None
    source_event_id: Optional[str] = None  # optional if your trace has per-event ids
    notes: Optional[str] = None

    # Optional extra context for triage (keep small, prefer hashes)
    tool_name: Optional[str] = None
    prompt_excerpt: Optional[str] = None
    prompt_hash: Optional[str] = None


@dataclass(frozen=True)
class EvidenceRefs:
    """
    Evidence references pointing back to the original trace.

    Prefer references + hashes, not full copies.
    """
    trace_path: Optional[str] = None
    event_seq: List[int] = field(default_factory=list)

    # Optional integrity helpers (best-effort)
    arg_hash: Optional[str] = None
    output_hash: Optional[str] = None


@dataclass(frozen=True)
class Snapshot:
    """
    Post-mortem snapshot (minimal, self-contained evidence).

    Rules:
      - ALWAYS redacted=True in v0.1
      - ALWAYS truncated
      - Keep <= ~800 chars per field by default
    """
    redacted: bool = True
    input_excerpt: Optional[str] = None
    output_excerpt: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class AuditFinding:
    """
    Side-effect boundary crossing finding (for audit reports)
    
    Represents a crossing event as an audit finding.
    This converts security logic into audit evidence.
    """
    finding_id: str
    ts: str  # ISO8601 timestamp
    crossing_type: str  # Side-effect type that crossed boundary (e.g., "filesystem.write")
    observed_category: str  # Observed category
    target: Optional[str] = None  # Target of the side-effect (path/host/command)
    tool: Optional[str] = None  # Tool that caused the crossing
    step_seq: Optional[int] = None  # Step sequence number
    step_id: Optional[str] = None  # Step ID
    allowed_categories: List[str] = field(default_factory=list)  # Allowed categories in boundary
    boundary: Optional[Dict[str, Any]] = None  # Boundary configuration snapshot


@dataclass(frozen=True)
class Finding:
    """
    One incident/finding derived from trace events.

    Core value: a human-readable, risk-mapped explanation with evidence references.
    """
    finding_id: str
    ts: str  # ISO8601 (UTC, with Z suffix recommended)
    severity: str  # "LOW" | "MED" | "HIGH" | "CRIT"
    title: str
    what_happened: str

    # Policy linkage (if available)
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None

    # OWASP Agentic Top 10 mapping (ASIxx)
    owasp_agentic_ids: List[str] = field(default_factory=list)

    # Cause-effect chain
    triggered_by: Optional[TriggeredBy] = None

    # Evidence pointers + optional snapshot
    evidence: EvidenceRefs = field(default_factory=EvidenceRefs)
    snapshot: Optional[Snapshot] = None

    # Optional: reproducible (if known)
    reproducible: Optional[bool] = None

    # Optional: suggested mitigation
    mitigation: Optional[str] = None

    # Free-form tags for future grouping/search (keep stable)
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Summary:
    tool_calls: int = 0
    denied: int = 0
    errors: int = 0
    warnings: int = 0

    # Optional: simple risk score (do not overfit in v0.1)
    risk_score: Optional[int] = None


@dataclass(frozen=True)
class EnvironmentMeta:
    """
    Minimal environment metadata for audit context.
    Keep it non-sensitive and stable.
    """
    failcore_version: Optional[str] = None
    python_version: str = platform.python_version()
    platform: str = platform.platform()
    hostname: str = sanitize_hostname(socket.gethostname() or "host")


@dataclass(frozen=True)
class AuditReport:
    schema: str = AUDIT_SCHEMA_V0_1_0
    report_id: str = field(default_factory=new_report_id)
    generated_at: str = field(default_factory=utc_now_iso)

    # IMPORTANT: run_id must be explicit for consistency across post-mortem analysis.
    run_id: str = field(default="")

    summary: Summary = field(default_factory=Summary)
    findings: List[Finding] = field(default_factory=list)

    integrity: IntegrityPlaceholder = field(default_factory=IntegrityPlaceholder)
    env: EnvironmentMeta = field(default_factory=EnvironmentMeta)

    # Optional: caller-provided metadata (normalized to JSON-safe primitives)
    metadata: JsonMeta = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "AuditReport":
        """
        Factory constructor to ensure run_id consistency and metadata normalization.

        Usage:
          report = AuditReport.new(run_id=trace_run_id, metadata={"service": "demo"})
        """
        rid = run_id or new_run_id()
        meta = normalize_metadata(metadata or {})
        return cls(run_id=rid, metadata=meta, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        # Ensure metadata is JSON-safe even if mutated upstream (defensive)
        d = asdict(self)
        d["metadata"] = normalize_metadata(d.get("metadata", {}))
        return d


# -------------------------
# Helpers for safe snapshots
# -------------------------

def make_snapshot(
    *,
    input_text: Optional[str],
    output_text: Optional[str],
    input_limit: int = 400,
    output_limit: int = 400,
    notes: Optional[str] = None,
) -> Snapshot:
    """
    Create a redacted/truncated snapshot.

    IMPORTANT: v0.1 always redacted=True. Do not store raw secrets here.
    """
    inp = truncate(input_text or "", input_limit) if input_text else None
    out = truncate(output_text or "", output_limit) if output_text else None
    return Snapshot(redacted=True, input_excerpt=inp, output_excerpt=out, notes=notes)


def hash_args_best_effort(args: Any, limit: int = 512) -> Optional[str]:
    """
    Best-effort hash of tool args to support integrity without storing full args.
    """
    if args is None:
        return None
    try:
        s = str(args)
    except Exception:
        return None
    s = truncate(s, limit)
    return sha256_text(s)
