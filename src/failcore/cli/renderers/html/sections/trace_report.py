# failcore/cli/renderers/html/sections/trace_report.py
"""
Trace Report specific sections
Aggregates logic from former summary.py (execution stats) and timeline.py
"""

import json
from typing import List
from failcore.cli.views.trace_report import TraceReportView, ReportStepView
from ..utils import (
    format_duration, format_provenance, highlight_json,
    get_status_color, get_risk_color, get_severity_color,
    format_params_for_timeline
)
from ..primitives import (
    render_copy_button, render_warning_indicator,
    render_replay_badge, render_provenance_badge, render_event_tag
)


def render_trace_summary_section(view: TraceReportView, overall_status_color: str) -> str:
    """Render the execution summary cards section"""
    
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


def render_timeline_section(steps: List[ReportStepView]) -> str:
    """Render the timeline section with all steps"""
    steps_html = _render_steps(steps)
    
    return f"""
        <section class="section">
            <h2>Timeline</h2>
            <div class="timeline">
                {steps_html}
            </div>
        </section>
    """


def _render_steps(steps: List[ReportStepView]) -> str:
    """Render all timeline steps"""
    steps_html = ""
    
    for idx, step in enumerate(steps, 1):
        status_color = get_status_color(step.status)
        # Use sanitized params for timeline display
        params_str = format_params_for_timeline(step.params)
        
        # Determine if this is a critical step (security event)
        is_critical = step.status in ["BLOCKED", "FAIL"]
        item_class = "critical" if is_critical else "normal"
        
        # Warning indicator for steps with warnings
        warning_indicator = ""
        if step.warnings or step.has_output_normalized:
            warning_indicator = ' ' + render_warning_indicator()
        
        # Replay badge for cached steps
        replay_badge = ""
        if step.replay_reused:
            replay_badge = ' ' + render_replay_badge()
        
        # Provenance badge (v0.1.2) - normalize display
        provenance_badge = ""
        if step.provenance and step.provenance != "LIVE":
            prov_display = format_provenance(step.provenance)
            provenance_badge = ' ' + render_provenance_badge(prov_display)
        
        # Details content
        details_html = _render_step_details(step)
        
        steps_html += f"""
            <div class="timeline-item {item_class}" onclick="toggleDetails('{step.step_id}')">
                <div class="timeline-row">
                    <span class="timeline-step-id">{step.step_id}</span>
                    <span class="timeline-tool">{step.tool}{warning_indicator}{provenance_badge}</span>
                    <span class="timeline-status" style="background-color: {status_color};">{step.status}{replay_badge}</span>
                    <span class="timeline-duration">{format_duration(step.duration_ms)}</span>
                    <span class="timeline-params">{params_str}</span>
                </div>
                {details_html}
            </div>
        """
    
    return steps_html


def _render_step_details(step: ReportStepView) -> str:
    """Render detailed information for a single step"""
    details_html = f'<div class="step-details" id="details-{step.step_id}">'
    
    # Tool metadata section (v0.1.2)
    if step.risk_level or step.side_effect:
        metadata_badges = []
        if step.risk_level:
            risk_color = get_risk_color(step.risk_level)
            metadata_badges.append(f'<span class="metadata-badge" style="background-color: {risk_color}20; color: {risk_color};">Risk: {step.risk_level.upper()}</span>')
        if step.side_effect:
            metadata_badges.append(f'<span class="metadata-badge">Side Effect: {step.side_effect.upper()}</span>')
        if step.severity:
            severity_color = get_severity_color(step.severity)
            metadata_badges.append(f'<span class="metadata-badge" style="background-color: {severity_color}20; color: {severity_color};">Severity: {step.severity}</span>')
        
        details_html += f"""
            <div class="detail-section">
                <div class="detail-label">Tool Metadata (v0.1.2)</div>
                <div class="metadata-badges">{"".join(metadata_badges)}</div>
            </div>
        """
    
    # Input parameters
    params_json = json.dumps(step.params, indent=2, ensure_ascii=False)
    params_json_highlighted = highlight_json(params_json)
    
    details_html += f"""
        <div class="detail-section">
            <div class="detail-label">
                Input Parameters
                {render_copy_button(f'params-{step.step_id}')}
            </div>
            <pre class="detail-code" id="params-{step.step_id}">{params_json_highlighted}</pre>
        </div>
    """
    
    # Output
    if step.output_value is not None:
        output_display = step.output_value
        full_output = json.dumps(step.output_value, indent=2, ensure_ascii=False)
        if len(str(output_display)) > 200:
            output_display = str(output_display)[:200] + "..."
        output_display_json = json.dumps(output_display, indent=2, ensure_ascii=False)
        output_highlighted = highlight_json(output_display_json)
        details_html += f"""
            <div class="detail-section">
                <div class="detail-label">
                    Output ({step.output_kind})
                    {render_copy_button(f'output-{step.step_id}')}
                </div>
                <pre class="detail-code" id="output-{step.step_id}">{output_highlighted}</pre>
                <div style="display:none;" id="output-full-{step.step_id}">{full_output}</div>
            </div>
        """
    
    # Error details (v0.1.2)
    if step.error_message:
        error_details = step.error_message
        if step.error_code:
            error_details = f"[{step.error_code}] {error_details}"
        if step.phase:
            error_details = f"{error_details}\nPhase: {step.phase}"
        
        details_html += f"""
            <div class="detail-section">
                <div class="detail-label">Error Details (v0.1.2)</div>
                <pre class="detail-code error">{error_details}</pre>
            </div>
        """
    
    # Warnings
    if step.warnings:
        warnings_str = ", ".join(step.warnings)
        details_html += f"""
            <div class="detail-section">
                <div class="detail-label">Warnings</div>
                <div class="warning-text">{warnings_str}</div>
            </div>
        """
    
    # Event tags
    event_tags = []
    if step.has_policy_denied:
        event_tags.append(render_event_tag('policy_denied'))
    if step.has_output_normalized:
        event_tags.append(render_event_tag('output_normalized', warning=True))
    
    if event_tags:
        details_html += f"""
            <div class="detail-section">
                <div class="detail-label">Trace Events</div>
                <div>{"".join(event_tags)}</div>
            </div>
        """
    
    details_html += "</div>"
    return details_html

