# failcore/core/guards/scanners/dlp.py
"""
DLP Scanner - Unified scanning entry point for DLP

This module provides the unified scanning interface for DLP.
Gate/Enricher should call scan_dlp(), not directly access DLP internals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..cache import ScanCache, ScannerID, ScanResult
from ..dlp.patterns import DLPPatternRegistry
from ..dlp.policies import DLPPolicy, PolicyMatrix


def scan_dlp(
    payload: Any,
    cache: Optional[ScanCache],
    step_id: Optional[str] = None,
    pattern_registry: Optional[DLPPatternRegistry] = None,
    policy_matrix: Optional[PolicyMatrix] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ScanResult:
    """
    Scan payload using DLP patterns
    
    This is the ONLY entry point for DLP scanning.
    Gate/Enricher should call this function, not directly access DLP internals.
    
    Args:
        payload: Payload to scan (dict, str, etc.)
        cache: ScanCache instance (required, writes result to cache)
        step_id: Optional step ID for trace association
        pattern_registry: Optional DLP pattern registry
        policy_matrix: Optional DLP policy matrix
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
    
    # Initialize components
    registry = pattern_registry or DLPPatternRegistry()
    matrix = policy_matrix or PolicyMatrix()
    
    # Scan payload for patterns
    # Convert payload to string for scanning
    payload_str = str(payload) if not isinstance(payload, str) else payload
    matches = registry.scan_text(payload_str)  # Returns List[tuple[str, SensitivePattern]]
    
    # Evaluate policy
    results = {
        "matches": [
            {
                "matched_text": matched_text,
                "pattern": pattern.name,
                "category": pattern.category.value,
                "severity": pattern.severity,
            }
            for matched_text, pattern in matches
        ],
        "match_count": len(matches),
        "max_severity": max((pattern.severity for _, pattern in matches), default=0) if matches else 0,
    }
    
    # Build evidence
    all_patterns = registry.get_all_patterns()
    evidence = {
        "scanner": "dlp",
        "patterns_checked": len(all_patterns),
        "matches_found": len(matches),
    }
    
    if matches:
        evidence["matched_patterns"] = [pattern.name for _, pattern in matches]
        evidence["matched_categories"] = list(set(pattern.category.value for _, pattern in matches))
    
    # Store result in cache (this is the ONLY place DLP results are stored)
    cache_key = cache.store_result(
        payload=payload,
        scanner_id=ScannerID.DLP,
        results=results,
        evidence=evidence,
        step_id=step_id,
        metadata={
            "scanner_version": "1.0.0",
        },
    )
    
    # Return result
    return cache.get_result(payload, ScannerID.DLP)


__all__ = [
    "scan_dlp",
]
