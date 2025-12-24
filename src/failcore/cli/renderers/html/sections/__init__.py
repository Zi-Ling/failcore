# failcore/cli/renderers/html/sections/__init__.py
"""
Section renderers for HTML reports
"""

from .summary import render_summary_section, render_security_impact_section
from .timeline import render_timeline_section
from .forensic import render_forensic_section

__all__ = [
    'render_summary_section',
    'render_security_impact_section',
    'render_timeline_section',
    'render_forensic_section',
]

