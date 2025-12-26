# failcore/cli/renderers/html/sections/__init__.py
"""
HTML Report Section Renderers
"""

from .common import render_card, render_section_container
from .trace_report import (
    render_trace_summary_section,
    render_security_impact_section,
    render_timeline_section
)
from .forensic_report import (
    render_forensic_section,
    render_forensic_audit_section
)

__all__ = [
    # Common
    'render_card',
    'render_section_container',
    
    # Trace Report
    'render_trace_summary_section',
    'render_security_impact_section',
    'render_timeline_section',
    
    # Forensic Report
    'render_forensic_section',
    'render_forensic_audit_section',
]
