# failcore/core/replay/drift/extract.py
"""
Parameter Snapshot Extractor - extracts parameter snapshots from trace events

Extracts tool call parameters from trace.jsonl events for drift detection.
"""

from typing import Dict, Any, List, Optional

from .types import ParamSnapshot


def extract_param_snapshots(events: List[Dict[str, Any]]) -> List[ParamSnapshot]:
    """
    Extract parameter snapshots from trace events
    
    Extracts parameters from STEP_START events, including:
    - tool_name
    - params (or args)
    - seq (sequence number)
    - ts (timestamp)
    - fingerprint (if available)
    - step_id (if available)
    
    Args:
        events: List of trace events (as dicts from trace.jsonl)
    
    Returns:
        List of ParamSnapshot objects (ordered by seq)
    """
    snapshots = []
    
    for event in events:
        evt = event.get("event", {})
        evt_type = evt.get("type")
        
        if evt_type != "STEP_START":
            continue
        
        # Extract step information
        step = evt.get("step", {})
        tool_name = step.get("tool", "")
        step_id = step.get("id")
        fingerprint = step.get("fingerprint")
        
        if not tool_name:
            continue  # Skip events without tool name
        
        # Extract parameters from payload
        # Try multiple paths: data.payload.input.summary, data.payload.input, step.params, etc.
        params = _extract_params(evt, step)
        
        # Extract metadata
        seq = event.get("seq", 0)
        ts = event.get("ts", "")
        
        snapshot = ParamSnapshot(
            tool_name=tool_name,
            params=params or {},
            seq=seq,
            ts=ts,
            fingerprint=fingerprint,
            step_id=step_id,
        )
        
        snapshots.append(snapshot)
    
    # Sort by sequence number
    snapshots.sort(key=lambda s: s.seq)
    
    return snapshots


def _extract_params(event: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract parameters from event data
    
    Tries multiple paths to find parameters:
    1. event.data.payload.input.summary (v0.1.2 format)
    2. event.data.payload.input (fallback)
    3. step.params (legacy format)
    4. step.data (alternative)
    
    Args:
        event: Event dictionary
        step: Step dictionary
    
    Returns:
        Parameters dictionary (empty dict if not found)
    """
    data = event.get("data", {})
    payload = data.get("payload", {})
    input_data = payload.get("input", {})
    
    # Try summary first (v0.1.2 format)
    if "summary" in input_data:
        params = input_data["summary"]
        if isinstance(params, dict):
            return params
    
    # Try direct input
    if isinstance(input_data, dict) and input_data:
        # Check if it looks like params (not just metadata)
        if not all(k in ("mode", "hash", "summary") for k in input_data.keys()):
            return input_data
    
    # Try step.params (legacy format)
    if "params" in step:
        params = step["params"]
        if isinstance(params, dict):
            return params
    
    # Try step.data
    step_data = step.get("data", {})
    if isinstance(step_data, dict) and step_data:
        return step_data
    
    return {}


__all__ = ["extract_param_snapshots"]
