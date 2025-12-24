# failcore/cli/renderers/html/primitives.py
"""
Primitive UI components for HTML rendering
"""

from typing import Optional


def render_badge(text: str, color: Optional[str] = None, style_class: str = "metadata-badge") -> str:
    """Render a badge component"""
    style = f' style="background-color: {color}20; color: {color};"' if color else ""
    return f'<span class="{style_class}"{style}>{text}</span>'


def render_copy_button(target_id: str) -> str:
    """Render a copy-to-clipboard button"""
    return f'<button class="copy-btn" onclick="copyToClipboard(\'{target_id}\', event)">Copy</button>'


def render_warning_indicator() -> str:
    """Render a warning indicator icon"""
    return '<span class="warning-indicator">⚠️</span>'


def render_replay_badge() -> str:
    """Render a replay cache badge"""
    return '<span class="replay-badge">REPLAYED</span>'


def render_provenance_badge(provenance_display: str) -> str:
    """Render a provenance badge"""
    return f'<span class="provenance-badge">{provenance_display}</span>'


def render_event_tag(text: str, warning: bool = False) -> str:
    """Render an event tag"""
    tag_class = "event-tag" + (" event-tag-warning" if warning else "")
    return f'<span class="{tag_class}">{text}</span>'


def render_icon(icon: str) -> str:
    """Render an icon (emoji)"""
    return icon

