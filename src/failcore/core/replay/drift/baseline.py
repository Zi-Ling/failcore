# failcore/core/replay/drift/baseline.py
"""
Baseline Generation - builds parameter baselines for drift detection

A baseline represents the initial or stable parameter behavior for a given tool.
For the first version, we use the first occurrence of each tool's parameters as the baseline.
"""

from typing import Dict, Any, List, Optional

from .types import ParamSnapshot
from .normalize import normalize_params
from .config import DriftConfig, get_default_config


def build_baseline(
    snapshots: List[ParamSnapshot],
    config: Optional[DriftConfig] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build baseline from parameter snapshots
    
    Baseline strategy (first version):
    - For each tool_name, use the first occurrence's normalized parameters as baseline
    - Baseline is immutable once established for a run
    - Returns Dict[tool_name, baseline_params]
    
    Args:
        snapshots: List of parameter snapshots (ordered by seq)
        config: Optional drift configuration (uses default if None)
    
    Returns:
        Dictionary mapping tool_name -> normalized baseline parameters
    """
    if config is None:
        config = get_default_config()
    
    baseline: Dict[str, Dict[str, Any]] = {}
    seen_tools: set = set()
    
    for snapshot in snapshots:
        tool_name = snapshot.tool_name
        
        # Skip if we already have a baseline for this tool
        if tool_name in seen_tools:
            continue
        
        # Normalize parameters
        normalized_params = normalize_params(
            snapshot.params,
            tool_name,
            config,
        )
        
        # Use first occurrence as baseline
        baseline[tool_name] = normalized_params
        seen_tools.add(tool_name)
    
    return baseline


def build_baseline_from_snapshots(
    snapshots: List[ParamSnapshot],
    config: Optional[DriftConfig] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build baseline from parameter snapshots (alias for build_baseline)
    
    This function is an alias for build_baseline to maintain API consistency.
    
    Args:
        snapshots: List of parameter snapshots
        config: Optional drift configuration
    
    Returns:
        Dictionary mapping tool_name -> normalized baseline parameters
    """
    return build_baseline(snapshots, config)


__all__ = ["build_baseline", "build_baseline_from_snapshots"]
