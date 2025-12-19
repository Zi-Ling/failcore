# failcore/core/executor/lifecycle.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceEventType(str, Enum):
    STEP_START = "STEP_START"
    STEP_OK = "STEP_OK"
    STEP_FAIL = "STEP_FAIL"


@dataclass(frozen=True)
class TraceEvent:
    """
    Minimal trace event for v0.1.
    Keep it JSON-serializable.
    """
    type: TraceEventType
    ts: str

    run_id: str
    step_id: str
    tool: str

    # Optional payload
    params_summary: Optional[Dict[str, Any]] = None
    output_summary: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None

    meta: Dict[str, Any] = field(default_factory=dict)
