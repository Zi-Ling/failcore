from __future__ import annotations

from typing import Any, Dict


def span_name_from_event(event: Any) -> str:
    """
    Derive a span name from a FailCore event.
    This function is intentionally conservative and schema-agnostic.
    """
    etype = getattr(event, "event_type", None) or getattr(event, "type", None)
    return f"failcore.{etype or 'event'}"


def attributes_from_event(event: Any) -> Dict[str, Any]:
    """
    Convert a FailCore event into OTel span attributes.

    We only extract shallow, stable fields to avoid tight coupling.
    """
    attrs: Dict[str, Any] = {}

    for key in (
        "run_id",
        "step_id",
        "event_type",
        "tool",
        "status",
        "rule_id",
    ):
        if hasattr(event, key):
            value = getattr(event, key)
            if value is not None:
                attrs[f"failcore.{key}"] = value

    return attrs


def is_error_event(event: Any) -> bool:
    """
    Best-effort detection of error-like events.
    """
    status = getattr(event, "status", None)
    level = getattr(event, "level", None)

    if status in {"ERROR", "FAIL", "DENIED"}:
        return True
    if level in {"ERROR", "FATAL"}:
        return True
    return False
