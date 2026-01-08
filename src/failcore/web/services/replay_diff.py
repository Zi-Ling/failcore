# failcore/web/services/replay_diff.py
"""
Replay Diff - argument difference computation

Computes differences between tool arguments across frames.
Only shows changes, not full JSON, to avoid overwhelming users.
"""

from typing import Dict, Any, List, Optional, Set


def diff_args(prev_args: Optional[Dict[str, Any]], curr_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute difference between previous and current arguments
    
    Returns a dict with:
    - "added": {key: value} - keys present in curr but not in prev
    - "modified": {key: {"old": value, "new": value}} - keys with different values
    - "deleted": {key: value} - keys present in prev but not in curr
    - "unchanged": {key: value} - keys with same values (optional, for reference)
    
    Args:
        prev_args: Previous frame's arguments (None if first frame)
        curr_args: Current frame's arguments
    
    Returns:
        Dictionary with diff structure
    """
    if prev_args is None:
        # First frame: all args are "added"
        return {
            "added": curr_args.copy(),
            "modified": {},
            "deleted": {},
        }
    
    prev_keys = set(prev_args.keys())
    curr_keys = set(curr_args.keys())
    
    added = {k: curr_args[k] for k in curr_keys - prev_keys}
    deleted = {k: prev_args[k] for k in prev_keys - curr_keys}
    
    modified = {}
    for k in prev_keys & curr_keys:
        prev_val = prev_args[k]
        curr_val = curr_args[k]
        if not _values_equal(prev_val, curr_val):
            modified[k] = {
                "old": prev_val,
                "new": curr_val,
            }
    
    return {
        "added": added,
        "modified": modified,
        "deleted": deleted,
    }


def _values_equal(val1: Any, val2: Any) -> bool:
    """
    Deep equality check for values
    
    Handles:
    - Primitive types (str, int, float, bool, None)
    - Lists (order matters)
    - Dicts (order doesn't matter)
    - Nested structures
    """
    if type(val1) != type(val2):
        return False
    
    if val1 is None or isinstance(val1, (str, int, float, bool)):
        return val1 == val2
    
    if isinstance(val1, list):
        if len(val1) != len(val2):
            return False
        return all(_values_equal(a, b) for a, b in zip(val1, val2))
    
    if isinstance(val1, dict):
        if set(val1.keys()) != set(val2.keys()):
            return False
        return all(_values_equal(val1[k], val2[k]) for k in val1.keys())
    
    # Fallback: string comparison
    return str(val1) == str(val2)


def format_diff_for_ui(diff: Dict[str, Any], show_unchanged: bool = False) -> Dict[str, Any]:
    """
    Format diff for UI display
    
    Args:
        diff: Diff dict from diff_args()
        show_unchanged: Whether to include unchanged fields
    
    Returns:
        Formatted diff dict suitable for UI rendering
    """
    result = {
        "added": diff.get("added", {}),
        "modified": diff.get("modified", {}),
        "deleted": diff.get("deleted", {}),
    }
    
    if show_unchanged:
        # Compute unchanged fields
        all_keys = set(diff.get("added", {}).keys()) | \
                   set(diff.get("modified", {}).keys()) | \
                   set(diff.get("deleted", {}).keys())
        # Note: We don't have access to unchanged fields here
        # This would require passing both prev and curr args
        result["unchanged"] = {}
    
    return result


def has_changes(diff: Dict[str, Any]) -> bool:
    """
    Check if diff has any changes
    
    Args:
        diff: Diff dict from diff_args()
    
    Returns:
        True if there are any changes
    """
    return bool(
        diff.get("added") or
        diff.get("modified") or
        diff.get("deleted")
    )


__all__ = [
    "diff_args",
    "format_diff_for_ui",
    "has_changes",
]
