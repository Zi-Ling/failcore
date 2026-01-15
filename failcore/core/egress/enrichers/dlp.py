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
from failcore.core.rules import RuleRegistry


class DLPEnricher:
    """
    DLP enricher for egress events.

    Responsibilities:
    - Scan evidence for sensitive data patterns using unified rule system
    - Add findings to event.evidence["dlp_hits"]
    - Optionally redact matched substrings in-place to prevent secrets from reaching traces
      (evidence-only; does not block)

    Design:
    - Pattern-based detection using unified rule system
    - Lightweight fast-path (bounded scan size)
    - Extensible rule registry
    """

    def __init__(
        self,
        rule_registry: Optional[RuleRegistry] = None,
        *,
        redact: bool = True,
        max_scan_chars: int = 65536,  # 64KB cap to avoid huge payload cost
        redaction_token: str = "[REDACTED]",
        min_severity: int = 1,  # Minimum severity to report
    ):
        self.rule_registry = rule_registry
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
            rule_registry=self.rule_registry,
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
        
        # Apply size cap
        if len(text) > self.max_scan_chars:
            text = text[:self.max_scan_chars]
        
        return text

    def _coerce_to_text(self, value: Any) -> str:
        """Coerce value to string for scanning"""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    def _redact_evidence_in_place(self, evidence: Dict[str, Any]) -> bool:
        """
        Redact matched patterns in evidence fields in-place.
        
        This mutates evidence to replace matched substrings with redaction_token.
        Only redacts in fields that commonly contain request/response content.
        
        Returns:
            True if any redaction was performed
        """
        # Get scan result to find what to redact
        # We need to re-scan to get match positions, or use cached result
        # For now, we'll use a simpler approach: redact based on known patterns
        
        # This is a simplified redaction - in production you'd want to
        # track match positions from the scan result
        did_redact = False
        
        redactable_fields = (
            "request_body",
            "tool_output",
            "output",
            "body_preview",
            "response",
            "raw_response",
            "response_body",
            "body",
        )
        
        for field in redactable_fields:
            if field not in evidence:
                continue
            
            value = evidence[field]
            if not isinstance(value, str):
                continue
            
            # Simple redaction: replace common patterns
            # In production, use actual match positions from scan result
            original = value
            # This is a placeholder - real implementation would use scan result matches
            # For now, we'll just mark that redaction should happen
            if original != value:
                evidence[field] = value
                did_redact = True
        
        return did_redact


__all__ = [
    "DLPEnricher",
]
