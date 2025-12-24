# failcore/cli/renderers/html/utils.py
"""
Utility functions for HTML rendering
"""

import json
import re
import os
from datetime import datetime
from typing import Any, Dict


def format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp to human-readable format"""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_timestamp


def format_duration(duration_ms: int) -> str:
    """Format duration with special handling for instant execution"""
    if duration_ms == 0:
        return "< 1ms"
    return f"{duration_ms}ms"


def format_provenance(provenance: str) -> str:
    """Format provenance string for display"""
    if not provenance or provenance == "LIVE":
        return ""
    # Normalize provenance display (USER, PLANNER, REPLAY_HIT, etc.)
    return provenance.replace("_", " ").title()


def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#x27;'))


def highlight_json(json_str: str) -> str:
    """Simple JSON syntax highlighting using regex"""
    import re
    
    # Escape HTML
    json_str = escape_html(json_str)
    
    # Highlight strings (including keys)
    json_str = re.sub(
        r'"([^"\\]*(\\.[^"\\]*)*)"',
        r'<span class="json-string">"</span><span class="json-string">\1</span><span class="json-string">"</span>',
        json_str
    )
    
    # Highlight keys (strings followed by colon)
    json_str = re.sub(
        r'<span class="json-string">"</span><span class="json-string">([^"]+)</span><span class="json-string">"</span>\s*:',
        r'<span class="json-key">"\1"</span>:',
        json_str
    )
    
    # Highlight numbers
    json_str = re.sub(r'\b(\d+\.?\d*)\b', r'<span class="json-number">\1</span>', json_str)
    
    # Highlight booleans
    json_str = re.sub(r'\b(true|false)\b', r'<span class="json-boolean">\1</span>', json_str)
    
    # Highlight null
    json_str = re.sub(r'\b(null)\b', r'<span class="json-null">\1</span>', json_str)
    
    return json_str


def get_status_color(status: str) -> str:
    """Get color code for step status"""
    colors = {
        "OK": "#10b981",      # green
        "BLOCKED": "#ef4444", # red
        "FAIL": "#f59e0b",    # amber
    }
    return colors.get(status, "#6b7280")


def get_risk_color(risk_level: str) -> str:
    """Get color code for risk level"""
    colors = {
        "low": "#10b981",
        "medium": "#f59e0b",
        "high": "#ef4444"
    }
    return colors.get(risk_level, "#6b7280")


def get_severity_color(severity: str) -> str:
    """Get color code for severity"""
    colors = {
        "INFO": "#3b82f6",
        "WARN": "#f59e0b",
        "ERROR": "#ef4444",
        "CRITICAL": "#dc2626"
    }
    return colors.get(severity, "#6b7280")


def sanitize_path(path: str, max_length: int = 60) -> str:
    """
    Sanitize and shorten path for display
    - Masks username in paths
    - Shows only last few segments if too long
    """
    # Mask common user directory patterns
    path = re.sub(r'\\Users\\[^\\]+\\', r'\\Users\\***\\', path)
    path = re.sub(r'/Users/[^/]+/', r'/Users/***/', path)
    path = re.sub(r'\\home\\[^\\]+\\', r'\\home\\***\\', path)
    path = re.sub(r'/home/[^/]+/', r'/home/***/', path)
    
    # If still too long, show last segments only
    if len(path) > max_length:
        parts = path.replace('\\', '/').split('/')
        if len(parts) > 3:
            # Keep last 2-3 segments
            return '.../' + '/'.join(parts[-2:])
    
    return path


def format_params_for_timeline(params: Dict[str, Any]) -> str:
    """
    Format parameters for timeline display
    - Sanitizes paths
    - Truncates long values
    """
    formatted_parts = []
    for k, v in params.items():
        str_val = str(v)
        
        # Sanitize if looks like a path
        if '\\' in str_val or '/' in str_val:
            str_val = sanitize_path(str_val, max_length=40)
        
        # Truncate if still too long
        if len(str_val) > 40:
            str_val = str_val[:37] + "..."
        
        formatted_parts.append(f"{k}={str_val}")
    
    return ", ".join(formatted_parts)

