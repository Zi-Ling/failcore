# failcore/core/guards/scanners/semantic.py
"""
Semantic Scanner - Unified scanning entry point for Semantic

This module provides the unified scanning interface for Semantic intent detection.
Gate/Enricher should call scan_semantic(), not directly access Semantic internals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..cache import ScanCache, ScannerID, ScanResult
from ..semantic.detectors import SemanticDetector
from failcore.core.rules import RuleRegistry, RuleSeverity


def scan_semantic(
    tool_name: str,
    params: Dict[str, Any],
    cache: Optional[ScanCache],
    step_id: Optional[str] = None,
    detector: Optional[SemanticDetector] = None,
    registry: Optional[RuleRegistry] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ScanResult:
    """
    Scan tool call using Semantic intent detection
    
    This is the ONLY entry point for Semantic scanning.
    Gate/Enricher should call this function, not directly access Semantic internals.
    
    Args:
        tool_name: Tool name
        params: Tool parameters
        cache: ScanCache instance (required, writes result to cache)
        step_id: Optional step ID for trace association
        detector: Optional Semantic detector
        registry: Optional rule registry
        context: Optional execution context
        
    Returns:
        ScanResult with Semantic scan results
        
    Notes:
        - Result is automatically stored in cache
        - Cache key: (payload_fingerprint, "semantic")
        - This is the ONLY producer of Semantic cache entries
    """
    if cache is None:
        raise ValueError("cache is required for Semantic scanning")
    
    # Create payload fingerprint (tool_name + params)
    payload = {"tool": tool_name, "params": params}
    
    # Check cache first
    cached = cache.get_result(payload, ScannerID.SEMANTIC)
    if cached is not None:
        return cached
    
    # Initialize components
    detector_instance = detector or SemanticDetector(
        rule_registry=registry or RuleRegistry(),
        min_severity=RuleSeverity.HIGH,
    )
    
    # Scan for semantic violations
    verdict = detector_instance.check(tool_name, params, context or {})
    
    # Build results
    results = {
        "action": verdict.action.value,
        "has_violations": verdict.has_violations,
        "violation_count": len(verdict.violations),
        "violations": [
            {
                "rule_id": v.rule_id,
                "name": v.name,
                "rule_category": v.category.value if hasattr(v.category, 'value') else str(v.category),
                "severity": v.severity.value if hasattr(v.severity, 'value') else str(v.severity),
                "description": v.description,
            }
            for v in verdict.violations
        ],
    }
    
    # Build evidence
    evidence = {
        "scanner": "semantic",
        "tool": tool_name,
        "action": verdict.action.value,
        "violations": len(verdict.violations),
    }
    
    if verdict.has_violations:
        evidence["violation_rules"] = [v.rule_id for v in verdict.violations]
        # Get max severity value (convert enum to int if needed)
        severity_values = []
        for v in verdict.violations:
            if hasattr(v.severity, 'value'):
                # RuleSeverity enum
                severity_map = {"critical": 10, "high": 8, "medium": 5, "low": 2}
                severity_values.append(severity_map.get(v.severity.value, 5))
            else:
                severity_values.append(5)  # Default
        evidence["max_severity"] = max(severity_values, default=0) if severity_values else 0
    
    # Store result in cache (this is the ONLY place Semantic results are stored)
    cache_key = cache.store_result(
        payload=payload,
        scanner_id=ScannerID.SEMANTIC,
        results=results,
        evidence=evidence,
        step_id=step_id,
        metadata={
            "scanner_version": "1.0.0",
            "verdict_explanation": verdict.get_explanation(),
        },
    )
    
    # Return result
    return cache.get_result(payload, ScannerID.SEMANTIC)


__all__ = [
    "scan_semantic",
]
