# failcore/core/egress/enrichers/dlp.py
"""
DLP Enricher - Data Loss Prevention scanning

Scans evidence text for sensitive data patterns and adds findings to evidence.
Optionally redacts matched substrings in-place to avoid leaking secrets into traces.

Outputs:
- event.evidence["dlp_hits"]: sorted list of pattern names that matched
- event.evidence["dlp_redacted"]: bool (only when redaction performed)
- event.evidence["dlp_pattern_categories"]: list of pattern categories detected
- event.evidence["dlp_max_severity"]: maximum severity of detected patterns
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Pattern, Set, Tuple
import re
import json

from ..types import EgressEvent
from failcore.core.rules import DLPPatternRegistry, SensitivePattern, PatternCategory


class DLPEnricher:
    """
    DLP enricher for egress events.

    Responsibilities:
    - Scan evidence for sensitive data patterns using guards/dlp pattern registry
    - Add findings to event.evidence["dlp_hits"]
    - Optionally redact matched substrings in-place to prevent secrets from reaching traces
      (evidence-only; does not block)

    Design:
    - Pattern-based detection using guards/dlp/patterns
    - Lightweight fast-path (bounded scan size)
    - Extensible pattern registry
    - Integrates with guards DLP module for consistency
    """

    def __init__(
        self,
        pattern_registry: Optional[DLPPatternRegistry] = None,
        patterns: Optional[Mapping[str, Pattern[str]]] = None,
        *,
        redact: bool = True,
        max_scan_chars: int = 65536,  # 64KB cap to avoid huge payload cost
        redaction_token: str = "[REDACTED]",
        min_severity: int = 1,  # Minimum severity to report
    ):
        # Use guards/dlp pattern registry if available
        self.pattern_registry = pattern_registry or DLPPatternRegistry()
        
        # Legacy support: accept raw patterns dict
        if patterns:
            # Convert legacy patterns to registry format
            for name, pattern in patterns.items():
                if name not in self.pattern_registry.get_all_patterns():
                    # Register as custom pattern
                    sensitive_pattern = SensitivePattern(
                        name=name,
                        category=PatternCategory.SECRET_TOKEN,
                        pattern=pattern,
                        severity=8,
                        description=f"Custom pattern: {name}"
                    )
                    self.pattern_registry.register_pattern(sensitive_pattern)
        
        # Get all patterns from registry
        self.patterns: Dict[str, Pattern[str]] = {
            name: pat.pattern
            for name, pat in self.pattern_registry.get_all_patterns().items()
        }
        
        self.redact = redact
        self.max_scan_chars = int(max_scan_chars) if max_scan_chars and max_scan_chars > 0 else 65536
        self.redaction_token = redaction_token
        self.min_severity = min_severity

    def enrich(self, event: EgressEvent) -> None:
        """
        Enrich event with DLP findings.

        Uses scan cache to avoid duplicate scanning if gate already scanned this payload.

        Adds:
          - event.evidence["dlp_hits"] = ["PATTERN_A", ...]
          - event.evidence["dlp_pattern_categories"] = ["api_key", "pii_email", ...]
          - event.evidence["dlp_max_severity"] = 10 (highest severity found)
        Optionally:
          - redacts secrets in-place inside certain evidence fields
          - event.evidence["dlp_redacted"] = True
        """
        evidence = getattr(event, "evidence", None)
        if not isinstance(evidence, dict):
            return

        # Extract text to scan (bounded)
        text = self._extract_text_for_scan(evidence)
        if not text or not text.strip():
            return

        # Get scan cache from event metadata (must be run-scoped)
        # Cache should be injected by RunCtx or executor
        scan_cache = getattr(event, "scan_cache", None)
        if scan_cache is None:
            # Try to get from event metadata
            metadata = getattr(event, "metadata", {})
            if isinstance(metadata, dict):
                scan_cache = metadata.get("scan_cache")
        
        # If no cache available, we need to create one (for enricher compatibility)
        # This is a fallback - ideally cache should be injected
        if scan_cache is None:
            from failcore.core.guards.cache import ScanCache
            run_id = getattr(event, "run_id", None) or "enricher_fallback"
            scan_cache = ScanCache(run_id=run_id)
        
        # Use scanners interface (this is the ONLY way to scan)
        from failcore.core.guards.scanners import scan_dlp
        
        step_id = getattr(event, "step_id", None)
        
        # Call scanner (will check cache first, then scan if needed)
        # scan_dlp accepts Any payload and converts to string internally
        scan_result = scan_dlp(
            payload=text,
            cache=scan_cache,
            step_id=step_id,
            pattern_registry=self.pattern_registry,
        )
        
        # Extract results from ScanResult
        results = scan_result.results
        matches = results.get("matches", [])
        
        # Extract pattern names from matches
        hits = set()
        for match in matches:
            pattern_name = match.get("pattern", "")
            if pattern_name:
                hits.add(pattern_name)
        
        if not hits:
            return
        
        # Extract evidence
        evidence_data = scan_result.evidence
        evidence["dlp_hits"] = sorted(hits)
        evidence["dlp_pattern_categories"] = evidence_data.get("matched_categories", [])
        evidence["dlp_max_severity"] = results.get("max_severity", 0)
        evidence["dlp_scan_cache_hit"] = scan_result.cache_key.payload_fingerprint is not None
        evidence["dlp_scan_hash"] = scan_result.cache_key.payload_fingerprint
        
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
        # Order matters: request_body first for pre_call, body_preview/tool_output for post_call
        for key in (
            "request_body",
            "tool_output",
            "output",
            "body_preview",
            "response",
            "raw_response",
            "response_body",
            "body",
        ):
            if key not in evidence:
                continue
            value = evidence.get(key)
            # Skip None, empty strings, and empty collections
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (dict, list)) and len(value) == 0:
                continue
            
            coerced = self._coerce_to_text(value)
            if coerced and coerced.strip():  # Only add non-empty strings
                parts.append(coerced)

        text = "\n".join(p for p in parts if p)
        if not text or not text.strip():
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


__all__ = ["DLPEnricher"]
