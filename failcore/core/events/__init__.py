"""
Core Events - Unified event model

Defines canonical event types that are consistent across both
preflight gate (tool boundary) and egress gate (proxy boundary).

Architecture principles:
1. ATTEMPT - Pre-execution event (written by gates before execution)
2. EGRESS - Post-execution event (written after execution completes)
3. Events from both boundaries share same schema structure
4. Only field availability differs, not structure

Event lifecycle:
- Preflight gate: ATTEMPT_START -> [execution] -> ATTEMPT_END -> EGRESS
- Egress gate: ATTEMPT_START -> EGRESS (combined)

Constraint:
- Every execution attempt MUST have stable attempt_id
- Verdict MUST be deterministically associated with attempt_id
"""

from .attempt import AttemptEvent, AttemptStatus, VerdictSchema, TargetSchema, TargetType
from .egress import EgressEvent, EvidenceSchema
from .envelope import TraceEnvelope, EventType

__all__ = [
    # Attempt events
    "AttemptEvent",
    "AttemptStatus",
    "VerdictSchema",
    "TargetSchema",
    "TargetType",
    # Egress events
    "EgressEvent",
    "EvidenceSchema",
    # Envelope
    "TraceEnvelope",
    "EventType",
]
