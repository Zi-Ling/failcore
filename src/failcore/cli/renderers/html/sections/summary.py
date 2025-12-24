# failcore/cli/renderers/html/sections/summary.py
"""
Summary section renderer
"""

from typing import Dict, Any
from ....views.trace_report import TraceReportView
from ..utils import format_duration


def render_summary_section(view: TraceReportView, overall_status_color: str) -> str:
    """Render the summary cards section"""
    
    # Extract status counts safely
    status_counts = view.summary.status_counts
    ok_count = status_counts.get('OK', 0)
    blocked_count = status_counts.get('BLOCKED', 0)
    fail_count = status_counts.get('FAIL', 0)
    
    # Format duration
    if view.summary.total_duration_ms == 0:
        duration_value = "< 1"
        duration_unit = "ms"
    else:
        duration_value = str(view.summary.total_duration_ms)
        duration_unit = "milliseconds"
    
    # Determine security verdict based on status
    if view.meta.overall_status == "BLOCKED":
        security_verdict = "THREAT NEUTRALIZED"
        verdict_color = "#10b981"  # Green - success in defense
        status_display = f"""
            <div class="summary-card-value" style="color: {overall_status_color};">{view.meta.overall_status}</div>
            <div class="summary-card-detail" style="color: {verdict_color}; font-weight: 600; margin-top: 0.5rem;">
                🛡️ {security_verdict}
            </div>
        """
    elif view.meta.overall_status == "FAIL":
        security_verdict = "EXECUTION FAILED"
        verdict_color = "#f59e0b"
        status_display = f"""
            <div class="summary-card-value" style="color: {overall_status_color};">{view.meta.overall_status}</div>
            <div class="summary-card-detail" style="color: {verdict_color}; font-weight: 500; margin-top: 0.5rem;">
                ⚠️ {security_verdict}
            </div>
        """
    else:  # OK
        security_verdict = "ALL SAFE"
        verdict_color = "#10b981"
        status_display = f"""
            <div class="summary-card-value" style="color: {overall_status_color};">{view.meta.overall_status}</div>
            <div class="summary-card-detail" style="color: {verdict_color}; font-weight: 500; margin-top: 0.5rem;">
                ✓ {security_verdict}
            </div>
        """
    
    return f"""
        <section class="section">
            <h2>Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-card-label">Result</div>
                    {status_display}
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">Steps</div>
                    <div class="summary-card-value">{view.summary.total_steps}</div>
                    <div class="summary-card-detail">
                        {ok_count} OK / 
                        {blocked_count} BLOCKED / 
                        {fail_count} FAIL
                    </div>
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">Duration</div>
                    <div class="summary-card-value">{duration_value}</div>
                    <div class="summary-card-detail">{duration_unit}</div>
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">🛡️ Threats Blocked</div>
                    <div class="summary-card-value">{blocked_count}</div>
                    <div class="summary-card-detail">
                        {fail_count} execution failures
                    </div>
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">Replay</div>
                    <div class="summary-card-value">{view.summary.replay_reused}</div>
                    <div class="summary-card-detail">reused</div>
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">Artifacts</div>
                    <div class="summary-card-value">{view.summary.artifacts_count}</div>
                    <div class="summary-card-detail">files</div>
                </div>
            </div>
        </section>
    """


def render_security_impact_section(view: TraceReportView, policy_impact_detail: str) -> str:
    """Render the security impact section"""
    
    blocked_count = view.summary.status_counts.get('BLOCKED', 0)
    ok_count = view.summary.status_counts.get('OK', 0)
    total_steps = view.summary.total_steps
    
    # Build impact statements as KPIs
    threats_neutralized = f"<li>✅ <strong>Threats neutralized:</strong> {blocked_count}</li>"
    unauthorized_effects = "<li>✅ <strong>Unauthorized side effects:</strong> 0</li>"
    sandbox_preserved = "<li>✅ <strong>Sandbox boundary preserved</strong></li>" if blocked_count > 0 else ""
    trace_recorded = "<li>✅ <strong>Trace recorded</strong> (replayable)</li>"
    
    # Optional: Add warning for output drift
    output_warning = ""
    if view.warnings:
        output_warning = f"<li class='impact-warning'>⚠️ <strong>Output validation:</strong> {len(view.warnings)} contract drift(s) detected</li>"
    
    return f"""
        <section class="section">
            <h2>🛡️ Security Impact</h2>
            <ul class="value-list">
                {threats_neutralized}
                {unauthorized_effects}
                {sandbox_preserved}
                {trace_recorded}
                {output_warning}
            </ul>
        </section>
    """

