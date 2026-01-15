# failcore/core/guards/scanners/dlp.py
"""
DLP Scanner - Unified scanning entry point for DLP

This module provides the unified scanning interface for DLP.
Gate/Enricher should call scan_dlp(), not directly access DLP internals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import json

from ..cache import ScanCache, ScannerID, ScanResult
from failcore.core.rules import RuleRegistry, RuleEngine, RuleCategory, RuleSeverity, RuleAction


def scan_dlp(
    payload: Any,
    cache: Optional[ScanCache],
    step_id: Optional[str] = None,
    rule_registry: Optional[RuleRegistry] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ScanResult:
    """
    Scan payload using DLP rules
    
    This is the ONLY entry point for DLP scanning.
    Gate/Enricher should call this function, not directly access DLP internals.
    
    Args:
        payload: Payload to scan (dict, str, etc.)
        cache: ScanCache instance (required, writes result to cache)
        step_id: Optional step ID for trace association
        rule_registry: Optional rule registry (will load DLP ruleset if not provided)
        context: Optional execution context
        
    Returns:
        ScanResult with DLP scan results
        
    Notes:
        - Result is automatically stored in cache
        - Cache key: (payload_fingerprint, "dlp")
        - This is the ONLY producer of DLP cache entries
    """
    if cache is None:
        raise ValueError("cache is required for DLP scanning")
    
    # Check cache first
    cached = cache.get_result(payload, ScannerID.DLP)
    if cached is not None:
        return cached
    
    # Initialize rule registry and engine
    if rule_registry is None:
        rule_registry = _get_default_dlp_registry()
    
    engine = RuleEngine(rule_registry, default_action=RuleAction.ALLOW)
    
    # Convert payload to string for scanning
    payload_str = str(payload) if not isinstance(payload, str) else payload
    
    # Convert payload to dict format for rule engine
    # Rule engine expects tool_name and params
    tool_params = _payload_to_tool_params(payload_str)
    
    # Evaluate using rule engine
    result = engine.evaluate(
        tool_name="__dlp_scan__",
        params=tool_params,
        context=context,
        categories=[
            RuleCategory.DLP_API_KEY,
            RuleCategory.DLP_SECRET,
            RuleCategory.DLP_PII,
            RuleCategory.DLP_PAYMENT,
        ],
    )
    
    # Convert rule matches to scan results format
    matches = []
    for match in result.matches:
        # Extract matched text from pattern
        matched_text = _extract_matched_text(payload_str, match.rule)
        
        # Map severity to numeric value
        severity_map = {
            RuleSeverity.CRITICAL: 10,
            RuleSeverity.HIGH: 8,
            RuleSeverity.MEDIUM: 5,
            RuleSeverity.LOW: 2,
        }
        
        matches.append({
            "matched_text": matched_text,
            "pattern": match.rule.name,
            "category": match.rule.category.value,
            "severity": severity_map.get(match.rule.severity, 5),
        })
    
    # Build results
    results = {
        "matches": matches,
        "match_count": len(matches),
        "max_severity": max((m["severity"] for m in matches), default=0) if matches else 0,
    }
    
    # Build evidence
    all_rules = rule_registry.get_rules_by_category(RuleCategory.DLP_API_KEY)
    all_rules.extend(rule_registry.get_rules_by_category(RuleCategory.DLP_SECRET))
    all_rules.extend(rule_registry.get_rules_by_category(RuleCategory.DLP_PII))
    all_rules.extend(rule_registry.get_rules_by_category(RuleCategory.DLP_PAYMENT))
    
    evidence = {
        "scanner": "dlp",
        "patterns_checked": len(all_rules),
        "matches_found": len(matches),
    }
    
    if matches:
        evidence["matched_patterns"] = [m["pattern"] for m in matches]
        evidence["matched_categories"] = list(set(m["category"] for m in matches))
    
    # Store result in cache (this is the ONLY place DLP results are stored)
    cache_key = cache.store_result(
        payload=payload,
        scanner_id=ScannerID.DLP,
        results=results,
        evidence=evidence,
        step_id=step_id,
        metadata={
            "scanner_version": "2.0.0",
        },
    )
    
    # Return result
    return cache.get_result(payload, ScannerID.DLP)


def _get_default_dlp_registry() -> RuleRegistry:
    """Get default DLP rule registry with ruleset loaded"""
    from failcore.infra.rulesets import FileSystemLoader
    from failcore.core.rules.loader import CompositeLoader
    from pathlib import Path
    
    # Try to load from default rulesets
    default_path = Path(__file__).parent.parent.parent.parent / "config" / "rulesets" / "default"
    
    loader = CompositeLoader([
        FileSystemLoader(Path.home() / ".failcore" / "rulesets"),
        FileSystemLoader(default_path),
    ])
    
    registry = RuleRegistry(loader)
    registry.load_ruleset("dlp")
    
    return registry


def _payload_to_tool_params(payload_str: str) -> Dict[str, Any]:
    """Convert payload string to tool params format"""
    # Try to parse as JSON first
    try:
        if isinstance(payload_str, str):
            parsed = json.loads(payload_str)
            if isinstance(parsed, dict):
                return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fallback: wrap in a dict
    return {
        "content": payload_str,
        "text": payload_str,
    }


def _extract_matched_text(text: str, rule) -> str:
    """Extract matched text from rule patterns"""
    # Try to find first match from patterns
    for pattern in rule.patterns:
        if pattern.compiled:
            match = pattern.compiled.search(text)
            if match:
                return match.group(0)
    
    # Fallback: return first 50 chars
    return text[:50] if len(text) > 50 else text


__all__ = [
    "scan_dlp",
]
