# failcore/core/replay/fingerprint.py
"""
Fingerprint computation for replay matching

Computes deterministic fingerprints for tool calls based on tool name and parameters.
This fingerprint is used to match current execution against historical traces.
"""

import json
import hashlib
from typing import Dict, Any


def compute_fingerprint(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute fingerprint for a tool call
    
    Fingerprint format: tool#params_hash (deterministic, not tied to run_id)
    This matches the logic in trace/builder.py for consistency.
    
    Args:
        tool: Tool name
        params: Tool parameters dict
    
    Returns:
        Fingerprint dict with:
        - id: fingerprint_id (format: tool#params_hash)
        - algo: hash algorithm ("sha256")
        - scope: scope description ("tool+params")
        - inputs: input details (tool, params_hash)
    """
    # Serialize params deterministically
    params_str = json.dumps(params, sort_keys=True)
    
    # Compute hash (first 16 chars for readability)
    params_hash = f"sha256:{hashlib.sha256(params_str.encode()).hexdigest()[:16]}"
    
    # Build fingerprint ID
    fingerprint_id = f"{tool}#{params_hash}"
    
    return {
        "id": fingerprint_id,
        "algo": "sha256",
        "scope": "tool+params",
        "inputs": {
            "tool": tool,
            "params_hash": params_hash,
        }
    }


__all__ = ["compute_fingerprint"]
