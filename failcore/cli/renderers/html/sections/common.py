# failcore/cli/renderers/html/sections/common.py
"""
Common HTML section components used by all report renderers
"""

from typing import Optional, Any


def render_card(label: str, value: Any, detail: Optional[str] = None, value_color: Optional[str] = None) -> str:
    """Render a standard summary card"""
    style_attr = f' style="color: {value_color};"' if value_color else ""
    detail_html = f'<div class="summary-card-detail">{detail}</div>' if detail else ""
    
    return f"""
        <div class="summary-card">
            <div class="summary-card-label">{label}</div>
            <div class="summary-card-value"{style_attr}>{value}</div>
            {detail_html}
        </div>
    """

def render_section_container(title: str, content: str, icon: Optional[str] = None, extra_classes: str = "") -> str:
    """Render a standard section container"""
    icon_html = f"{icon} " if icon else ""
    return f"""
        <section class="section {extra_classes}">
            <h2>{icon_html}{title}</h2>
            {content}
        </section>
    """

