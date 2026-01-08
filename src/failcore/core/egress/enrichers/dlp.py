# failcore/core/egress/enrichers/dlp.py
"""
DLP Enricher - Data Loss Prevention scanning

Scans evidence text for sensitive data patterns and adds findings to evidence.
Optionally redacts matched substrings in-place to avoid leaking secrets into traces.

Outputs:
- event.evidence["dlp_hits"]: sorted list of pattern names that matched
- event.evidence["dlp_redacted"]: bool (only when redaction performed)
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Pattern, Set, Tuple
import re
import json

from ..types import EgressEvent


# Common DLP patterns (simplified for v1)
DLP_PATTERNS: Dict[str, Pattern[str]] = {
    "OPENAI_API_KEY": re.compile(r"sk-[A-Za-z0-9]{48}"),
    "AWS_ACCESS_KEY": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GITHUB_TOKEN": re.compile(r"gh[ps]_[A-Za-z0-9]{36}"),
    # Handles:
    # - -----BEGIN PRIVATE KEY-----
    # - -----BEGIN RSA PRIVATE KEY-----
    # - -----BEGIN DSA PRIVATE KEY-----
    # - -----BEGIN EC PRIVATE KEY-----
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA|DSA|EC)? ?PRIVATE KEY-----"),
}


class DLPEnricher:
    """
    DLP enricher for egress events.

    Responsibilities:
    - Scan evidence for sensitive data patterns
    - Add findings to event.evidence["dlp_hits"]
    - Optionally redact matched substrings in-place to prevent secrets from reaching traces
      (evidence-only; does not block)

    Design:
    - Pattern-based detection
    - Lightweight fast-path (bounded scan size)
    - Extensible pattern registry
    """

    def __init__(
        self,
        patterns: Optional[Mapping[str, Pattern[str]]] = None,
        *,
        redact: bool = True,
        max_scan_chars: int = 65536,  # 64KB cap to avoid huge payload cost
        redaction_token: str = "[REDACTED]",
    ):
        self.patterns: Dict[str, Pattern[str]] = dict(patterns) if patterns else dict(DLP_PATTERNS)
        self.redact = redact
        self.max_scan_chars = int(max_scan_chars) if max_scan_chars and max_scan_chars > 0 else 65536
        self.redaction_token = redaction_token

    def enrich(self, event: EgressEvent) -> None:
        """
        Enrich event with DLP findings.

        Adds:
          - event.evidence["dlp_hits"] = ["PATTERN_A", ...]
        Optionally:
          - redacts secrets in-place inside certain evidence fields
          - event.evidence["dlp_redacted"] = True
        """
        evidence = getattr(event, "evidence", None)
        if not isinstance(evidence, dict):
            return

        # Extract text to scan (bounded)
        text = self._extract_text_for_scan(evidence)
        if not text:
            return

        hits: Set[str] = set()
        for name, pattern in self.patterns.items():
            try:
                if pattern.search(text):
                    hits.add(name)
            except re.error:
                # If a bad pattern slips in, don't crash the pipeline
                continue

        if not hits:
            return

        evidence["dlp_hits"] = sorted(hits)

        # Optional redaction: mutate evidence to reduce secret leakage in traces
        if self.redact:
            did_redact = self._redact_evidence_in_place(evidence)
            if did_redact:
                evidence["dlp_redacted"] = True

    # ----------------------------
    # Scanning helpers
    # ----------------------------

    def _extract_text_for_scan(self, evidence: Dict[str, Any]) -> str:
        """
        Extract a bounded text blob from evidence for scanning.
        """
        parts: List[str] = []

        # Prefer scanning fields that commonly contain request/response content
        for key in (
            "tool_output",
            "output",
            "request_body",
            "body_preview",
            "response",
            "raw_response",
            "response_body",
            "body",
        ):
            if key not in evidence:
                continue
            parts.append(self._coerce_to_text(evidence.get(key)))

        text = "\n".join(p for p in parts if p)
        if not text:
            return ""

        # Cap scan size (fast-path friendly)
        if len(text) > self.max_scan_chars:
            text = text[: self.max_scan_chars]
        return text

    def _coerce_to_text(self, value: Any) -> str:
        """
        Best-effort conversion to text for scanning.
        Avoids crashing on weird types and keeps JSON-ish structures readable.
        """
        if value is None:
            return ""

        if isinstance(value, str):
            return value

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if isinstance(value, dict):
            # Common case: response dict contains nested bytes in "body"
            # Convert bytes to string inside dict safely before dumping
            safe = self._json_sanitize(value)
            try:
                return json.dumps(safe, ensure_ascii=False)
            except Exception:
                return str(safe)

        if isinstance(value, (list, tuple)):
            safe = self._json_sanitize(value)
            try:
                return json.dumps(safe, ensure_ascii=False)
            except Exception:
                return str(safe)

        # Fallback
        return str(value)

    def _json_sanitize(self, obj: Any) -> Any:
        """
        Make an object JSON-serializable in a conservative way.
        - bytes -> decoded text
        - dict/list -> recurse
        - other -> keep as-is (json.dumps may still fallback to str later)
        """
        if obj is None:
            return None
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return {str(k): self._json_sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._json_sanitize(x) for x in obj]
        return obj

    # ----------------------------
    # Redaction helpers
    # ----------------------------

    def _redact_text(self, text: str) -> Tuple[str, bool]:
        """
        Apply all patterns to redact text.
        Returns (redacted_text, did_redact).
        """
        if not text:
            return text, False

        did = False
        out = text

        for _, pattern in self.patterns.items():
            try:
                # Replace matched substrings with token
                new = pattern.sub(self.redaction_token, out)
                if new != out:
                    did = True
                    out = new
            except re.error:
                continue

        return out, did

    def _redact_evidence_in_place(self, evidence: Dict[str, Any]) -> bool:
        """
        Redact secrets in-place inside selected evidence fields.
        We intentionally do NOT attempt to walk arbitrary object graphs:
        keep it safe and predictable.
        """
        did_any = False

        # Redact common string/bytes holders
        for key in ("request_body", "body_preview", "output"):
            if key in evidence:
                did = self._redact_value_in_place(evidence, key)
                did_any = did_any or did

        # Redact tool_output (often dict/json/bytes)
        if "tool_output" in evidence:
            did = self._redact_value_in_place(evidence, "tool_output")
            did_any = did_any or did

        # Redact response containers
        # Common pattern: evidence["response"] is dict containing "body"
        if "response" in evidence and isinstance(evidence["response"], dict):
            resp = evidence["response"]
            # redact nested body/preview fields if present
            for k in ("body", "body_preview", "text", "content"):
                if k in resp:
                    did = self._redact_nested_value(resp, k)
                    did_any = did_any or did

        # Also handle top-level raw/response_body/body if used by producers
        for key in ("raw_response", "response_body", "body"):
            if key in evidence:
                did = self._redact_value_in_place(evidence, key)
                did_any = did_any or did

        return did_any

    def _redact_value_in_place(self, container: Dict[str, Any], key: str) -> bool:
        v = container.get(key)

        if v is None:
            return False

        # str
        if isinstance(v, str):
            red, did = self._redact_text(v)
            if did:
                container[key] = red
            return did

        # bytes
        if isinstance(v, bytes):
            txt = v.decode("utf-8", errors="replace")
            red, did = self._redact_text(txt)
            if did:
                container[key] = red  # store as str to keep JSONL safe
            return did

        # dict/list: sanitize to JSON text, redact that, store redacted string
        # (This prevents secrets inside nested dicts leaking into JSONL)
        if isinstance(v, (dict, list, tuple)):
            txt = self._coerce_to_text(v)
            red, did = self._redact_text(txt)
            if did:
                container[key] = red
            return did

        # other types: stringify & redact
        txt = str(v)
        red, did = self._redact_text(txt)
        if did:
            container[key] = red
        return did

    def _redact_nested_value(self, container: Dict[str, Any], key: str) -> bool:
        v = container.get(key)
        if v is None:
            return False

        if isinstance(v, str):
            red, did = self._redact_text(v)
            if did:
                container[key] = red
            return did

        if isinstance(v, bytes):
            txt = v.decode("utf-8", errors="replace")
            red, did = self._redact_text(txt)
            if did:
                container[key] = red
            return did

        if isinstance(v, (dict, list, tuple)):
            txt = self._coerce_to_text(v)
            red, did = self._redact_text(txt)
            if did:
                container[key] = red
            return did

        txt = str(v)
        red, did = self._redact_text(txt)
        if did:
            container[key] = red
        return did


__all__ = ["DLPEnricher", "DLP_PATTERNS"]
