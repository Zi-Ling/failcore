# failcore/cli/renderers/html/__init__.py
"""
HTML renderer for Views - Generate standalone HTML reports

This module is refactored into multiple components:
- utils: Utility functions for formatting and highlighting
- primitives: Atomic UI components (badges, buttons, etc.)
- styles: CSS and JavaScript resources
- sections: Large UI sections (summary, timeline, forensic)
- layout: HTML document structure
"""

from ...views.trace_report import TraceReportView
from .utils import format_timestamp, get_status_color
from .sections import (
    render_summary_section,
    render_security_impact_section,
    render_timeline_section,
    render_forensic_section
)
from .layout import render_html_document


class HtmlRenderer:
    """
    HTML renderer for report views
    
    Generates clean, standalone HTML with embedded CSS/JS.
    No external dependencies required.
    """
    
    def render_trace_report(self, view: TraceReportView) -> str:
        """Render TraceReportView as HTML"""
        
        # Format created_at
        created_at_display = format_timestamp(view.meta.created_at)
        
        # Get overall status color
        overall_status_color = get_status_color(view.meta.overall_status)
        
        # Generate policy impact detail for Security Impact section
        policy_impact_detail = ""
        if view.policy_details:
            first_policy = view.policy_details[0]
            policy_impact_detail = f" ({first_policy['rule_id']}: {first_policy['reason']})"
        
        # Get sandbox root from metadata
        sandbox_root = view.meta.workspace or ".failcore/sandbox"
        
        # Render main sections
        summary_html = render_summary_section(view, overall_status_color)
        security_impact_html = render_security_impact_section(view, policy_impact_detail)
        timeline_html = render_timeline_section(view.steps)
        forensic_html = render_forensic_section(view.failures, view.warnings, sandbox_root)
        
        # Combine all sections
        content_html = f"""
{summary_html}
{security_impact_html}
{timeline_html}
{forensic_html}
        """
        
        # Generate complete HTML document
        return render_html_document(
            view=view,
            created_at_display=created_at_display,
            content_html=content_html,
        )


# Export the renderer for backward compatibility
__all__ = ['HtmlRenderer']

