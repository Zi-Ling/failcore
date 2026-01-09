# failcore/cli/renderers/html/base.py
"""
HTML renderer for Views - Generate standalone HTML reports

This module is refactored into multiple components:
- utils: Utility functions for formatting and highlighting
- primitives: Atomic UI components (badges, buttons, etc.)
- styles: CSS and JavaScript resources
- sections: Large UI sections (summary, timeline, audit)
- layout: HTML document structure
"""

from failcore.cli.views.trace_report import TraceReportView
from failcore.cli.views.audit_report import AuditReportView
from .utils import format_timestamp, get_status_color
from .sections import (
    render_trace_summary_section,
    render_security_impact_section,
    render_timeline_section,
    render_audit_section
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
        
        # Render main sections
        summary_html = render_trace_summary_section(view, overall_status_color)
        security_impact_html = render_security_impact_section(view, policy_impact_detail)
        timeline_html = render_timeline_section(view.steps)
        
        # Note: Audit section is now a separate report (use 'failcore audit' command)
        # audit_html = render_audit_section(view)  # Removed - audit is independent
        
        # Combine all sections
        content_html = f"""
{summary_html}
{security_impact_html}
{timeline_html}
        """
        
        # Generate complete HTML document
        return render_html_document(
            view=view,
            created_at_display=created_at_display,
            content_html=content_html,
        )

    def render_audit_report(self, view: AuditReportView) -> str:
        """Render AuditReportView as HTML"""
        # Note: Reusing render_html_document requires adapting the view or updating layout.
        # For now, we'll adapt the AuditReportView to something layout understands or extend layout.
        # Since layout expects TraceReportView for header/footer, we need a slight adaptation.
        
        # Create a mock TraceReportView for layout compatibility
        # In a full refactor, layout should accept a generic meta interface.
        from failcore.cli.views.trace_report import ReportMeta
        
        meta_adapter = ReportMeta(
            run_id=view.meta.run_id,
            created_at=view.meta.generated_at,
            workspace=view.meta.report_id, # abusing field for display
            trace_path=view.meta.trace_path,
            overall_status="AUDIT", # Special status for audit report
        )
        
        # For layout compatibility (it accesses view.meta attributes directly)
        class ViewAdapter:
            def __init__(self, meta):
                self.meta = meta
        
        view_adapter = ViewAdapter(meta_adapter)
        
        created_at_display = format_timestamp(view.meta.generated_at)
        
        # Render the specific audit content
        content_html = render_audit_section(view)
        
        return render_html_document(
            view=view_adapter, # type: ignore
            created_at_display=created_at_display,
            content_html=content_html,
        )


# Export the renderer for backward compatibility
__all__ = ['HtmlRenderer']

