# failcore/cli/renderers/html/sections/base.py
"""
HTML Report Section Renderers
"""

from .common import render_card, render_section_container
from .trace_report import (
    render_trace_summary_section,
    render_security_impact_section,
    render_timeline_section
)
from .audit_report import (
    render_audit_section
)

__all__ = [
    # Common
    'render_card',
    'render_section_container',
    
    # Trace Report
    'render_trace_summary_section',
    'render_security_impact_section',
    'render_timeline_section',
    
    # audit Report
    'render_audit_section'
]
