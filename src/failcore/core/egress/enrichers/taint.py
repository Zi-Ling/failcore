# failcore/core/egress/enrichers/taint.py
"""
Taint Enricher - Weak taint tracking for attribution

Labels data source origin (user/model/tool/system) for replay and attribution.

Goal:
- Provide a lightweight, best-effort taint label on each EgressEvent
- Avoid crashing the pipeline if evidence is malformed
- Keep output JSON-serializable and stable for downstream consumers

Output:
- event.evidence["taint_source"]: "user" | "model" | "tool" | "system" | "unknown"
- event.evidence["taint_confidence"]: "high" | "medium" | "low" (optional but useful)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..types import EgressEvent


class TaintEnricher:
    """
    Weak taint enricher for attribution.

    Responsibilities:
    - Infer likely origin of data in this event (user/model/tool/system/unknown)
    - Add taint_source (+ optional confidence) into event.evidence
    - Never block traffic; never throw

    Design:
    - Weak taint (no full propagation)
    - Heuristics only, explicitly low-risk
    - Defensive about evidence types
    """

    def enrich(self, event: EgressEvent) -> None:
        evidence = getattr(event, "evidence", None)
        if evidence is None:
            evidence = {}
            event.evidence = evidence  # type: ignore[assignment]
        if not isinstance(evidence, dict):
            return

        source, confidence = self._infer_taint_source(event, evidence)

        # Only write stable JSON-safe values
        evidence["taint_source"] = source
        if confidence:
            evidence["taint_confidence"] = confidence

    # ----------------------------
    # Inference
    # ----------------------------

    def _infer_taint_source(self, event: EgressEvent, evidence: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        Infer taint source from event + evidence.

        Returns:
            (source, confidence)
            source: "user" | "model" | "tool" | "system" | "unknown"
            confidence: "high" | "medium" | "low" | None
        """
        # 1) Explicit override (highest priority)
        explicit = self._get_str(evidence, "taint_source") or self._get_str(evidence, "input_source")
        if explicit:
            normalized = self._normalize_source(explicit)
            return normalized, "high"

        # 2) If the event is clearly tied to a named tool, it's usually model-driven tool use
        tool_name = getattr(event, "tool_name", None)
        if isinstance(tool_name, str) and tool_name.strip():
            # If evidence suggests user-triggered tool invocation, mark user
            if self._looks_user_initiated(evidence):
                return "user", "medium"
            return "model", "medium"

        # 3) Presence of chat messages with role=user suggests user-originated content
        if self._evidence_has_user_messages(evidence):
            return "user", "medium"

        # 4) Upstream/proxy request bodies are typically user+system initiated
        # If request_body exists but no tool_name, assume user by default
        if "request_body" in evidence:
            return "user", "low"

        # 5) System events (heuristic)
        if self._looks_system_event(event, evidence):
            return "system", "low"

        # 6) Default (do not assume model if we have no signals)
        return "unknown", "low"

    # ----------------------------
    # Heuristics helpers
    # ----------------------------

    def _normalize_source(self, s: str) -> str:
        v = s.strip().lower()
        if v in ("user", "human"):
            return "user"
        if v in ("model", "assistant", "llm"):
            return "model"
        if v in ("tool", "function", "action"):
            return "tool"
        if v in ("system", "framework", "runtime"):
            return "system"
        return "unknown"

    def _get_str(self, d: Dict[str, Any], key: str) -> Optional[str]:
        v = d.get(key)
        if isinstance(v, str) and v.strip():
            return v
        return None

    def _looks_user_initiated(self, evidence: Dict[str, Any]) -> bool:
        """
        Best-effort: detect whether the tool call appears explicitly user-triggered.
        """
        # explicit flags
        if evidence.get("user_initiated") is True:
            return True
        origin = self._get_str(evidence, "origin") or self._get_str(evidence, "source")
        if origin and origin.strip().lower() in ("user", "human"):
            return True
        return False

    def _evidence_has_user_messages(self, evidence: Dict[str, Any]) -> bool:
        """
        Detect OpenAI-like chat payloads containing role=user.
        We avoid json parsing to keep this lightweight.
        """
        # common keys where messages might live
        candidates = (
            evidence.get("request_body"),
            evidence.get("body_preview"),
            evidence.get("tool_input"),
            evidence.get("input"),
        )

        for v in candidates:
            # Quick string scan (fast)
            if isinstance(v, str):
                if '"role":"user"' in v.replace(" ", "") or "'role':'user'" in v.replace(" ", ""):
                    return True
            elif isinstance(v, dict):
                msgs = v.get("messages")
                if isinstance(msgs, list):
                    for m in msgs:
                        if isinstance(m, dict) and (m.get("role") == "user"):
                            return True
        return False

    def _looks_system_event(self, event: EgressEvent, evidence: Dict[str, Any]) -> bool:
        """
        Mark some events as system-originated when they look like internal framework telemetry.
        """
        # If your EgressEvent has a type/kind/egress field, you can add stronger checks here.
        kind = getattr(event, "kind", None) or getattr(event, "event_type", None)
        if isinstance(kind, str) and kind.lower() in ("internal", "telemetry", "heartbeat"):
            return True
        if evidence.get("internal") is True:
            return True
        return False


__all__ = ["TaintEnricher"]
