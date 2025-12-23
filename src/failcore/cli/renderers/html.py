# failcore/cli/renderers/html.py
"""
HTML renderer for Views - Generate standalone HTML reports
"""

import json
from datetime import datetime
from ..views.trace_report import TraceReportView


class HtmlRenderer:
    """
    HTML renderer for report views
    
    Generates clean, standalone HTML with embedded CSS/JS.
    No external dependencies required.
    """
    
    def render_trace_report(self, view: TraceReportView) -> str:
        """Render TraceReportView as HTML"""
        
        # Format created_at
        created_at_display = view.meta.created_at
        try:
            dt = datetime.fromisoformat(view.meta.created_at.replace("Z", "+00:00"))
            created_at_display = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        
        # Status colors
        status_colors = {
            "OK": "#10b981",      # green
            "BLOCKED": "#ef4444", # red
            "FAIL": "#f59e0b",    # amber
        }
        
        overall_status_color = status_colors.get(view.meta.overall_status, "#6b7280")
        
        # Generate steps HTML
        steps_html = self._render_steps(view.steps, status_colors)
        
        # Generate failures and warnings HTML
        failure_warning_html = self._render_failures_and_warnings(view.failures, view.warnings)
        
        # Generate policy details for Execution Impact
        policy_impact_detail = ""
        if view.policy_details:
            first_policy = view.policy_details[0]
            policy_impact_detail = f" ({first_policy['rule_id']}: {first_policy['reason']})"
        
        # Generate complete HTML
        return self._render_full_html(
            view=view,
            created_at_display=created_at_display,
            overall_status_color=overall_status_color,
            steps_html=steps_html,
            failure_warning_html=failure_warning_html,
            policy_impact_detail=policy_impact_detail,
        )
    
    def _render_steps(self, steps, status_colors):
        """Render timeline steps"""
        steps_html = ""
        
        for idx, step in enumerate(steps, 1):
            status_color = status_colors.get(step.status, "#6b7280")
            params_str = ", ".join(f"{k}={v}" for k, v in step.params.items())
            
            # Warning indicator for steps with warnings
            warning_indicator = ""
            if step.warnings or step.has_output_normalized:
                warning_indicator = ' <span class="warning-indicator">⚠️</span>'
            
            # Replay badge for cached steps
            replay_badge = ""
            if step.replay_reused:
                replay_badge = ' <span class="replay-badge">REPLAYED</span>'
            
            # Details content
            params_json = json.dumps(step.params, indent=2, ensure_ascii=False)
            details_html = f"""
                <div class="step-details" id="details-{step.step_id}">
                    <div class="detail-section">
                        <div class="detail-label">
                            Input Parameters
                            <button class="copy-btn" onclick="copyToClipboard('params-{step.step_id}', event)">Copy</button>
                        </div>
                        <pre class="detail-code" id="params-{step.step_id}">{params_json}</pre>
                    </div>
            """
            
            if step.output_value is not None:
                output_display = step.output_value
                full_output = json.dumps(step.output_value, indent=2, ensure_ascii=False)
                if len(str(output_display)) > 200:
                    output_display = str(output_display)[:200] + "..."
                output_display_json = json.dumps(output_display, indent=2, ensure_ascii=False)
                details_html += f"""
                    <div class="detail-section">
                        <div class="detail-label">
                            Output ({step.output_kind})
                            <button class="copy-btn" onclick="copyToClipboard('output-{step.step_id}', event)">Copy</button>
                        </div>
                        <pre class="detail-code" id="output-{step.step_id}">{output_display_json}</pre>
                        <div style="display:none;" id="output-full-{step.step_id}">{full_output}</div>
                    </div>
                """
            
            if step.error_message:
                details_html += f"""
                    <div class="detail-section">
                        <div class="detail-label">Error Message</div>
                        <pre class="detail-code error">{step.error_message}</pre>
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
                event_tags.append('<span class="event-tag">policy_denied</span>')
            if step.has_output_normalized:
                event_tags.append('<span class="event-tag event-tag-warning">output_normalized</span>')
            
            if event_tags:
                details_html += f"""
                    <div class="detail-section">
                        <div class="detail-label">Trace Events</div>
                        <div>{"".join(event_tags)}</div>
                    </div>
                """
            
            details_html += "</div>"
            
            steps_html += f"""
                <div class="timeline-item" onclick="toggleDetails('{step.step_id}')">
                    <div class="timeline-row">
                        <span class="timeline-step-id">{step.step_id}</span>
                        <span class="timeline-tool">{step.tool}{warning_indicator}</span>
                        <span class="timeline-status" style="background-color: {status_color};">{step.status}{replay_badge}</span>
                        <span class="timeline-duration">{step.duration_ms}ms</span>
                        <span class="timeline-params">{params_str}</span>
                    </div>
                    {details_html}
                </div>
            """
        
        return steps_html
    
    def _render_failures_and_warnings(self, failures, warnings):
        """Render failure and warning details section"""
        if not failures and not warnings:
            return ""
        
        sections_html = ""
        
        # Render failures
        if failures:
            failure_items = ""
            for failure in failures:
                failure_type = "POLICY_DENY" if failure.has_policy_denied else "EXECUTION_ERROR"
                failure_detail = f"<strong>Message:</strong> {failure.error_message}"
                
                # Add policy details if available
                if failure.rule_id:
                    failure_detail = f"<strong>Policy:</strong> {failure.policy_id or 'N/A'} / {failure.rule_id}<br>{failure_detail}"
                
                failure_items += f"""
                    <div class="failure-item">
                        <div class="failure-field"><strong>Step:</strong> {failure.step_id}</div>
                        <div class="failure-field"><strong>Type:</strong> {failure_type}</div>
                        <div class="failure-field">{failure_detail}</div>
                    </div>
                """
            
            sections_html += f"""
                <div class="failure-detail">
                    <div class="detail-subtitle">Failures</div>
                    {failure_items}
                </div>
            """
        
        # Render warnings
        if warnings:
            warning_items = ""
            for warning in warnings:
                warning_type = "OUTPUT_KIND_MISMATCH" if warning.has_output_normalized else "GENERAL_WARNING"
                warning_detail = ""
                
                if warning.has_output_normalized and warning.expected_kind:
                    warning_detail = f"""
                        <strong>Expected:</strong> {warning.expected_kind.upper()}<br>
                        <strong>Observed:</strong> {warning.observed_kind.upper()}<br>
                        <strong>Reason:</strong> {warning.normalize_reason or 'N/A'}
                    """
                elif warning.warnings:
                    warning_detail = f"<strong>Warnings:</strong> {', '.join(warning.warnings)}"
                
                warning_items += f"""
                    <div class="warning-item">
                        <div class="failure-field"><strong>Step:</strong> {warning.step_id}</div>
                        <div class="failure-field"><strong>Type:</strong> {warning_type}</div>
                        <div class="failure-field">{warning_detail}</div>
                    </div>
                """
            
            sections_html += f"""
                <div class="warning-detail">
                    <div class="detail-subtitle">Warnings</div>
                    {warning_items}
                </div>
            """
        
        return f"""
            <section class="section">
                <h2>Failure / Warning Details</h2>
                {sections_html}
            </section>
        """
    
    def _render_full_html(self, view, created_at_display, overall_status_color, steps_html, failure_warning_html, policy_impact_detail):
        """Render complete HTML document"""
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FailCore Execution Report - {view.meta.run_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.5;
            color: #1f2937;
            background: #f9fafb;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem 2.5rem;
        }}
        
        .header h1 {{
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        
        .header-info {{
            display: flex;
            gap: 2rem;
            margin-top: 1rem;
            font-size: 0.875rem;
            opacity: 0.95;
        }}
        
        .header-info-item {{
            display: flex;
            flex-direction: column;
        }}
        
        .header-info-label {{
            opacity: 0.8;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .header-info-value {{
            font-weight: 600;
            margin-top: 0.25rem;
        }}
        
        /* Section */
        .section {{
            padding: 2rem 2.5rem;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        .section:last-child {{
            border-bottom: none;
        }}
        
        .section h2 {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            color: #111827;
        }}
        
        /* Summary */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.5rem;
        }}
        
        .summary-card {{
            background: #f9fafb;
            border-radius: 8px;
            padding: 1.25rem;
            border: 1px solid #e5e7eb;
        }}
        
        .summary-card-label {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b7280;
            margin-bottom: 0.5rem;
        }}
        
        .summary-card-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #111827;
        }}
        
        .summary-card-detail {{
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 0.25rem;
        }}
        
        /* Value proposition */
        .value-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .value-list li {{
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            font-size: 0.9375rem;
        }}
        
        .value-list li::before {{
            content: "✓";
            color: #10b981;
            font-weight: 700;
            font-size: 1.125rem;
            flex-shrink: 0;
        }}
        
        .value-list li.impact-warning::before {{
            content: "";
        }}
        
        /* Timeline */
        .timeline {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        
        .timeline-item {{
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .timeline-item:hover {{
            border-color: #d1d5db;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }}
        
        .timeline-row {{
            display: grid;
            grid-template-columns: 100px 1fr 100px 80px 2fr;
            gap: 1rem;
            padding: 0.875rem 1.25rem;
            align-items: center;
            font-size: 0.875rem;
        }}
        
        .timeline-step-id {{
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-weight: 600;
            color: #6b7280;
        }}
        
        .timeline-tool {{
            font-weight: 500;
            color: #111827;
        }}
        
        .timeline-status {{
            text-align: center;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            color: white;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            justify-content: center;
        }}
        
        .replay-badge {{
            background: #3b82f6;
            color: white;
            padding: 0.125rem 0.5rem;
            border-radius: 3px;
            font-size: 0.625rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            white-space: nowrap;
        }}
        
        .timeline-duration {{
            color: #6b7280;
            text-align: right;
        }}
        
        .timeline-params {{
            color: #6b7280;
            font-size: 0.8125rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        /* Step details */
        .step-details {{
            display: none;
            background: #f9fafb;
            padding: 1.25rem;
            border-top: 1px solid #e5e7eb;
        }}
        
        .step-details.expanded {{
            display: block;
        }}
        
        .detail-section {{
            margin-bottom: 1rem;
        }}
        
        .detail-section:last-child {{
            margin-bottom: 0;
        }}
        
        .detail-label {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b7280;
            margin-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .copy-btn {{
            background: #3b82f6;
            color: white;
            border: none;
            padding: 0.25rem 0.625rem;
            border-radius: 4px;
            font-size: 0.6875rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .copy-btn:hover {{
            background: #2563eb;
        }}
        
        .copy-btn:active {{
            background: #1d4ed8;
        }}
        
        .copy-btn.copied {{
            background: #10b981;
        }}
        
        .detail-code {{
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 0.8125rem;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            padding: 0.75rem;
            overflow-x: auto;
            color: #111827;
        }}
        
        .detail-code.error {{
            color: #dc2626;
            border-color: #fecaca;
            background: #fef2f2;
        }}
        
        .event-tag {{
            display: inline-block;
            padding: 0.25rem 0.625rem;
            background: #dbeafe;
            color: #1e40af;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-right: 0.5rem;
        }}
        
        .event-tag-warning {{
            background: #fef3c7;
            color: #92400e;
        }}
        
        .warning-indicator {{
            font-size: 0.875rem;
        }}
        
        .warning-text {{
            color: #f59e0b;
            font-size: 0.875rem;
            font-weight: 500;
        }}
        
        /* Failure detail */
        .failure-detail {{
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 6px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }}
        
        .failure-detail:last-child {{
            margin-bottom: 0;
        }}
        
        .failure-item {{
            margin-bottom: 1rem;
        }}
        
        .failure-item:last-child {{
            margin-bottom: 0;
        }}
        
        .failure-field {{
            margin-bottom: 0.5rem;
            font-size: 0.9375rem;
        }}
        
        /* Warning detail */
        .warning-detail {{
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-radius: 6px;
            padding: 1.25rem;
        }}
        
        .warning-item {{
            margin-bottom: 1rem;
        }}
        
        .warning-item:last-child {{
            margin-bottom: 0;
        }}
        
        .detail-subtitle {{
            font-size: 0.875rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #374151;
            margin-bottom: 1rem;
        }}
        
        /* Footer */
        .footer {{
            padding: 1.5rem 2.5rem;
            background: #f9fafb;
            border-top: 1px solid #e5e7eb;
            font-size: 0.8125rem;
            color: #6b7280;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .footer-item {{
            display: flex;
            flex-direction: column;
        }}
        
        .footer-label {{
            font-weight: 600;
            color: #9ca3af;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .footer-value {{
            color: #4b5563;
            margin-top: 0.25rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>FailCore Execution Report</h1>
            <div class="header-info">
                <div class="header-info-item">
                    <span class="header-info-label">Run ID</span>
                    <span class="header-info-value">{view.meta.run_id}</span>
                </div>
                <div class="header-info-item">
                    <span class="header-info-label">Created</span>
                    <span class="header-info-value">{created_at_display}</span>
                </div>
                <div class="header-info-item">
                    <span class="header-info-label">Trace</span>
                    <span class="header-info-value">{view.meta.trace_path or 'N/A'}</span>
                </div>
            </div>
        </div>
        
        <!-- Summary -->
        <section class="section">
            <h2>Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-card-label">Status</div>
                    <div class="summary-card-value" style="color: {overall_status_color};">{view.meta.overall_status}</div>
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">Steps</div>
                    <div class="summary-card-value">{view.summary.total_steps}</div>
                    <div class="summary-card-detail">
                        {view.summary.status_counts.get('OK', 0)} OK / 
                        {view.summary.status_counts.get('BLOCKED', 0)} BLOCKED / 
                        {view.summary.status_counts.get('FAIL', 0)} FAIL
                    </div>
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">Duration</div>
                    <div class="summary-card-value">{view.summary.total_duration_ms}</div>
                    <div class="summary-card-detail">milliseconds</div>
                </div>
                
                <div class="summary-card">
                    <div class="summary-card-label">Blocked</div>
                    <div class="summary-card-value">{view.summary.status_counts.get('BLOCKED', 0)}</div>
                    <div class="summary-card-detail">
                        {view.summary.status_counts.get('FAIL', 0)} failed
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
        
        <!-- Value / Savings -->
        <section class="section">
            <h2>Execution Impact</h2>
            <ul class="value-list">
                <li>{view.value_metrics.unsafe_actions_blocked} unsafe action(s) blocked by policy{policy_impact_detail}</li>
                <li>0 side effects occurred</li>
                <li>Full trace recorded for offline replay</li>
                {"<li class='impact-warning'>⚠️ " + str(len(view.warnings)) + " output contract drift(s) detected</li>" if view.warnings else ""}
            </ul>
        </section>
        
        <!-- Timeline -->
        <section class="section">
            <h2>Timeline</h2>
            <div class="timeline">
                {steps_html}
            </div>
        </section>
        
        <!-- Failure / Warning Detail -->
        {failure_warning_html}
        
        <!-- Footer -->
        <div class="footer">
            <div class="footer-item">
                <span class="footer-label">Generated by</span>
                <span class="footer-value">FailCore v0.1.1</span>
            </div>
            <div class="footer-item">
                <span class="footer-label">Workspace</span>
                <span class="footer-value">{view.meta.workspace or 'N/A'}</span>
            </div>
        </div>
    </div>
    
    <script>
        function toggleDetails(stepId) {{
            const details = document.getElementById('details-' + stepId);
            if (details.classList.contains('expanded')) {{
                details.classList.remove('expanded');
            }} else {{
                // Close other expanded items
                document.querySelectorAll('.step-details.expanded').forEach(el => {{
                    el.classList.remove('expanded');
                }});
                details.classList.add('expanded');
            }}
        }}
        
        function copyToClipboard(elementId, event) {{
            event.stopPropagation(); // Prevent toggle
            
            const element = document.getElementById(elementId);
            const button = event.target;
            
            if (!element) return;
            
            // Get text content
            const text = element.textContent || element.innerText;
            
            // Copy to clipboard
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(text).then(() => {{
                    // Visual feedback
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    button.classList.add('copied');
                    
                    setTimeout(() => {{
                        button.textContent = originalText;
                        button.classList.remove('copied');
                    }}, 2000);
                }}).catch(err => {{
                    console.error('Failed to copy:', err);
                    alert('Failed to copy to clipboard');
                }});
            }} else {{
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                
                try {{
                    document.execCommand('copy');
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    button.classList.add('copied');
                    
                    setTimeout(() => {{
                        button.textContent = originalText;
                        button.classList.remove('copied');
                    }}, 2000);
                }} catch (err) {{
                    console.error('Failed to copy:', err);
                    alert('Failed to copy to clipboard');
                }} finally {{
                    document.body.removeChild(textarea);
                }}
            }}
        }}
    </script>
</body>
</html>"""

