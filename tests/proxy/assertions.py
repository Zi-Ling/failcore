"""
Strict JSON structure assertions for proxy tests

Replace string-based checks with structured assertions.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """
    Read JSONL file and return list of events
    
    Args:
        path: Path to JSONL file
    
    Returns:
        List of parsed JSON objects (excluding trace headers)
    """
    events = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                # Skip trace headers
                if event.get("type") == "trace_header":
                    continue
                # Accept egress_event or any other event type
                events.append(event)
            except json.JSONDecodeError as e:
                # Log but continue (might be malformed line)
                continue
    return events


def assert_has_event(
    events: List[Dict[str, Any]],
    event_type: Optional[str] = None,
    egress: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Assert that events list contains an event matching criteria
    
    Args:
        events: List of event dicts
        event_type: Expected event type (e.g., "egress_event")
        egress: Expected egress type (e.g., "NETWORK", "COST")
        **kwargs: Additional field matches
    
    Returns:
        Matching event dict
    
    Raises:
        AssertionError: If no matching event found
    """
    for event in events:
        # Check type
        if event_type and event.get("type") != event_type:
            continue
        
        # Check egress
        if egress:
            event_egress = event.get("egress")
            if isinstance(event_egress, str):
                if event_egress != egress:
                    continue
            elif isinstance(event_egress, dict):
                if event_egress.get("value") != egress:
                    continue
            else:
                continue
        
        # Check additional fields
        match = True
        for key, value in kwargs.items():
            # Support nested keys (e.g., "evidence.usage")
            if "." in key:
                parts = key.split(".")
                current = event
                for part in parts:
                    if not isinstance(current, dict) or part not in current:
                        match = False
                        break
                    current = current[part]
                if match and current != value:
                    match = False
            else:
                if event.get(key) != value:
                    match = False
        
        if match:
            return event
    
    # Build error message
    criteria = []
    if event_type:
        criteria.append(f"type={event_type}")
    if egress:
        criteria.append(f"egress={egress}")
    criteria.extend([f"{k}={v}" for k, v in kwargs.items()])
    
    raise AssertionError(
        f"No event found matching: {', '.join(criteria)}\n"
        f"Available events: {len(events)} total"
    )


def assert_event_fields(
    event: Dict[str, Any],
    required: Optional[List[str]] = None,
    forbidden: Optional[List[str]] = None,
    exact: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Assert event has required fields and lacks forbidden fields
    
    Args:
        event: Event dict to check
        required: List of required field paths (supports nested: "evidence.usage")
        forbidden: List of forbidden field paths
        exact: Dict of exact field values to match
    
    Raises:
        AssertionError: If assertions fail
    """
    def get_nested_value(obj: Dict, path: str) -> Any:
        """Get nested value by dot path"""
        parts = path.split(".")
        current = obj
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current
    
    # Check required fields
    if required:
        missing = []
        for field in required:
            value = get_nested_value(event, field)
            if value is None:
                missing.append(field)
        if missing:
            raise AssertionError(f"Missing required fields: {missing}")
    
    # Check forbidden fields
    if forbidden:
        present = []
        for field in forbidden:
            value = get_nested_value(event, field)
            if value is not None:
                present.append(field)
        if present:
            raise AssertionError(f"Forbidden fields present: {present}")
    
    # Check exact values
    if exact:
        mismatches = []
        for field, expected_value in exact.items():
            actual_value = get_nested_value(event, field)
            if actual_value != expected_value:
                mismatches.append(f"{field}: expected {expected_value}, got {actual_value}")
        if mismatches:
            raise AssertionError(f"Field value mismatches: {mismatches}")


__all__ = ["read_jsonl", "assert_has_event", "assert_event_fields"]
