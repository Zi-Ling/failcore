# failcore/core/guards/scanners/taint.py
"""
Taint Scanner - Unified scanning entry point for Taint tracking

This module provides the unified scanning interface for Taint tracking.
Gate/Enricher should call scan_taint(), not directly access Taint internals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

from ..cache import ScanCache, ScannerID, ScanResult
from ..taint.context import TaintContext
from ..taint.tag import TaintTag, DataSensitivity, TaintSource


def scan_taint(
    tool_name: str,
    params: Dict[str, Any],
    cache: Optional[ScanCache],
    step_id: Optional[str] = None,
    taint_context: Optional[TaintContext] = None,
    dependencies: Optional[list] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ScanResult:
    """
    Scan tool call for taint tracking
    
    This is the ONLY entry point for Taint scanning.
    Gate/Enricher should call this function, not directly access Taint internals.
    
    Args:
        tool_name: Tool name
        params: Tool parameters
        cache: ScanCache instance (required, writes result to cache)
        step_id: Optional step ID for trace association
        taint_context: Optional taint context
        dependencies: Optional dependencies (for detecting tainted inputs)
        context: Optional execution context
        
    Returns:
        ScanResult with Taint scan results
        
    Notes:
        - Result is automatically stored in cache
        - Cache key: (payload_fingerprint, "taint")
        - This is the ONLY producer of Taint cache entries
    """
    if cache is None:
        raise ValueError("cache is required for Taint scanning")
    
    # Create payload fingerprint (tool_name + params)
    payload = {"tool": tool_name, "params": params}
    
    # Check cache first
    cached = cache.get_result(payload, ScannerID.TAINT)
    if cached is not None:
        return cached
    
    # Initialize components
    taint_ctx = taint_context or TaintContext()
    
    # Detect tainted inputs (if this is a sink tool)
    taint_tags: Set[TaintTag] = set()
    is_sink = taint_ctx.is_sink_tool(tool_name)
    is_source = taint_ctx.is_source_tool(tool_name)
    
    if is_sink and dependencies:
        taint_tags = taint_ctx.detect_tainted_inputs(params, dependencies)
    
    # Build results
    results = {
        "is_sink": is_sink,
        "is_source": is_source,
        "taint_tags_count": len(taint_tags),
        "taint_tags": [
            {
                "source": tag.source.value if hasattr(tag.source, 'value') else str(tag.source),
                "sensitivity": tag.sensitivity.value if hasattr(tag.sensitivity, 'value') else str(tag.sensitivity),
            }
            for tag in taint_tags
        ],
    }
    
    # Build evidence
    evidence = {
        "scanner": "taint",
        "tool": tool_name,
        "is_sink": is_sink,
        "is_source": is_source,
        "taint_detected": len(taint_tags) > 0,
    }
    
    if taint_tags:
        max_sensitivity = max(
            (tag.sensitivity.value if hasattr(tag.sensitivity, 'value') else 0 for tag in taint_tags),
            default=0
        )
        evidence["max_sensitivity"] = max_sensitivity
        evidence["taint_sources"] = list(set(
            tag.source.value if hasattr(tag.source, 'value') else str(tag.source)
            for tag in taint_tags
        ))
    
    # Store result in cache (this is the ONLY place Taint results are stored)
    cache_key = cache.store_result(
        payload=payload,
        scanner_id=ScannerID.TAINT,
        results=results,
        evidence=evidence,
        step_id=step_id,
        metadata={
            "scanner_version": "1.0.0",
        },
    )
    
    # Return result
    return cache.get_result(payload, ScannerID.TAINT)


__all__ = [
    "scan_taint",
]
