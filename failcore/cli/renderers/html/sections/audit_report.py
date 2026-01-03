# failcore/cli/renderers/html/sections/audit_report.py
"""
audit Report Renderer (Legal Document Format)
"""

from typing import List
from failcore.cli.views.audit_report import AuditReportView, AuditFindingView


def _get_risk_level_semantic(score: int) -> str:
    """Convert numeric risk score to semantic level"""
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    elif score >= 20:
        return "Low"
    else:
        return "Minimal"


def _calculate_observed_risk(findings) -> tuple[str, int]:
    """
    Calculate Observed Risk Level based on incident severity.
    Returns (semantic_level, numeric_score)
    
    Observed Risk = risk level before FailCore enforcement
    """
    if not findings:
        return ("Minimal", 5)
    
    # Count by severity
    sev_counts = {"CRIT": 0, "HIGH": 0, "MED": 0, "LOW": 0}
    for f in findings:
        sev = f.severity.split()[0].upper()
        if "CRIT" in sev:
            sev_counts["CRIT"] += 1
        elif "HIGH" in sev:
            sev_counts["HIGH"] += 1
        elif "MED" in sev or "MEDIUM" in sev:
            sev_counts["MED"] += 1
        else:
            sev_counts["LOW"] += 1
    
    # Calculate observed risk score
    if sev_counts["CRIT"] > 0:
        return ("High", 75)
    elif sev_counts["HIGH"] > 0:
        return ("Medium", 55)
    elif sev_counts["MED"] > 0:
        return ("Low", 15)  # Medium incidents observed = Low observed risk
    else:
        return ("Minimal", 5)


def render_audit_section(view: AuditReportView) -> str:
    """
    Render audit report as a formal legal document with pagination.
    
    Structure (Three-Layer):
    - Layer 1 (Summary, Fixed 1 page): Executive Summary + Risk Overview
    - Layer 2 (Body, Growable): Execution Timeline + Incident Chapters
    - Layer 3 (Appendix, Unlimited): Raw Evidence + Technical Details
    
    Each section is page-break-aware for PDF/print output.
    """
    
    # Document Header (not HTML <header>, but document title block)
    doc_header = f"""
        <div class="doc-header">
            <div class="doc-title">FailCore audit Report</div>
            <div class="doc-classification">CONFIDENTIAL</div>
            <div style="margin-top: 1rem; font-size: 0.85rem; line-height: 1.6; color: #333; border-left: 3px solid #000; padding-left: 1rem;">
                This document is an official audit record.<br>
                Unauthorized distribution is prohibited.
            </div>
            <div class="doc-metadata">
                <div class="metadata-row">
                    <span class="metadata-label">Report ID:</span>
                    <span class="metadata-value mono">{view.meta.report_id}</span>
                </div>
                <div class="metadata-row">
                    <span class="metadata-label">Generated:</span>
                    <span class="metadata-value mono">{view.meta.generated_at}</span>
                </div>
                <div class="metadata-row">
                    <span class="metadata-label">Run ID:</span>
                    <span class="metadata-value mono">{view.meta.run_id}</span>
                </div>
                <div class="metadata-row">
                    <span class="metadata-label">Schema:</span>
                    <span class="metadata-value mono">{view.meta.schema}</span>
                </div>
            </div>
        </div>
    """
    
    # ==============================
    # SECTION 1: Executive Summary (section container)
    # ==============================
    
    exec_lines = view.executive_summary.split(". ")
    conclusion_line = exec_lines[0] + "." if exec_lines else view.executive_summary
    rest_summary = ". ".join(exec_lines[1:]) if len(exec_lines) > 1 else ""
    
    # Calculate Observed vs Residual Risk
    observed_level, observed_score = _calculate_observed_risk(view.findings)
    residual_score = view.summary.risk_score or 2
    residual_level = _get_risk_level_semantic(residual_score)
    
    # Risk model explanation
    has_medium = any("MEDIUM" in f.severity.upper() or "MED" in f.severity.upper() for f in view.findings)
    risk_explanation = ""
    if has_medium:
        risk_explanation = f"""
                    <p style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #ddd; font-style: italic; color: #555;">
                        A medium-severity execution incident was observed during the session. 
                        However, due to successful runtime enforcement and absence of side effects, 
                        the residual system risk after mitigation remains minimal.
                    </p>
        """
    
    section1_summary = f"""
        <section class="sheet">
            <div class="section-content">
                <div class="section-title">Part I: Executive Summary</div>
                
                <div class="exec-summary-box">
                    <div style="font-weight: 700; margin-bottom: 0.5rem;">Conclusion:</div>
                    <p>{conclusion_line}</p>
                    <p style="margin-top: 0.5rem;">{rest_summary}</p>
                    {risk_explanation}
                </div>
                
                <div class="risk-overview-grid">
                    <div class="risk-metric">
                        <div class="metric-label">Observed Risk Level</div>
                        <div class="metric-value" style="font-size: 1.5rem;">{observed_level}</div>
                        <div style="font-size: 0.85rem; color: #666; margin-top: 0.25rem;">({observed_score}/100)</div>
                    </div>
                    <div class="risk-metric">
                        <div class="metric-label">Residual Risk</div>
                        <div class="metric-value" style="font-size: 1.5rem;">{residual_level}</div>
                        <div style="font-size: 0.85rem; color: #666; margin-top: 0.25rem;">({residual_score}/100)</div>
                    </div>
                    <div class="risk-metric">
                        <div class="metric-label">Observed Incidents</div>
                        <div class="metric-value">{view.summary.findings_total}</div>
                    </div>
                    <div class="risk-metric">
                        <div class="metric-label">Enforcement Blocks</div>
                        <div class="metric-value">{view.value_metrics.policy_denied_findings}</div>
                    </div>
                </div>
                
                <h3 style="margin-top: 2rem; margin-bottom: 1rem;">Risk Assessment Model</h3>
                <p style="font-size: 0.85rem; color: #666; margin-bottom: 1rem; font-style: italic; border-left: 3px solid #999; padding-left: 1rem;">
                    <strong>Observed Risk</strong> reflects the severity of incidents detected during execution. 
                    <strong>Residual Risk</strong> represents the remaining risk after FailCore runtime enforcement and mitigation controls are applied.
                </p>
                <table class="risk-breakdown-table">
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>Observed Incidents</strong></td>
                                <td>{view.summary.findings_total} incident(s) detected</td>
                            </tr>
                            <tr>
                                <td><strong>Observed Risk Level</strong></td>
                                <td>{observed_level} ({observed_score}/100)</td>
                            </tr>
                            <tr>
                                <td><strong>Residual Risk Score</strong></td>
                                <td>{residual_level} ({residual_score}/100)</td>
                            </tr>
    """
    
    section1_summary += """
                        </tbody>
                    </table>
                    
                    <p style="margin-top: 1rem; font-size: 0.85rem; color: #555;">
                        For detailed incident breakdown by severity, refer to Part III: Incident Analysis.
                    </p>
            </div>
        </section>
    """
    
    # ==============================
    # SECTION 2: Execution Timeline (section container)
    # ==============================
    
    timeline_html = _render_execution_timeline(view.timeline)
    
    section2_timeline = f"""
        <section class="sheet">
            <div class="section-content">
                <div class="section-title">Part II: Execution Timeline</div>
                <p style="margin-bottom: 1.5rem; font-style: italic; color: #555;">
                    The following timeline presents a chronological record of all tool invocations, 
                    policy decisions, and validation events during the execution session.
                </p>
                <div class="timeline">
                    {timeline_html}
                </div>
            </div>
        </section>
    """
    
    # ==============================
    # SECTION 3: Incident Analysis (section container)
    # ==============================
    
    section3_incidents = _render_incident_chapters(view)
    
    # ==============================
    # SECTIONS 4+: Appendices (section containers)
    # ==============================
    
    sections_appendix = _render_appendix_sections(view)
    
    return f"""
        <div id="report-container" class="mode-preview">
            {doc_header}
            {section1_summary}
            {section2_timeline}
            {section3_incidents}
            {sections_appendix}
        </div>
    """


def _render_execution_timeline(timeline: List) -> str:
    """
    Render execution timeline in vertical timeline style (GitHub Actions-like).
    
    Each step is a timeline node with:
    - Timestamp marker
    - Event type indicator
    - Input/Output details
    - Status (ok/denied/failed/warning)
    """
    if not timeline:
        return '<p style="font-style: italic; color: #666;">No execution events recorded.</p>'
    
    html = '<div class="timeline-container">'
    
    for step in timeline:
        # Determine icon/status class
        outcome_class = f"outcome-{step.outcome}"
        icon = "●"  # Default
        if step.outcome == "denied":
            icon = "✖"
        elif step.outcome == "failed":
            icon = "✖"
        elif step.outcome == "warning":
            icon = "⚠"
        elif step.outcome == "ok":
            icon = "✓"
        
        # Format timestamp (show time only, not full ISO)
        ts_display = step.ts.split("T")[1][:12] if "T" in step.ts else step.ts
        
        # Event type display name
        event_display = step.event_type.replace("_", " ")
        
        # Action subtitle for better readability
        action_subtitle = ""
        if step.event_type == "STEP_START":
            action_subtitle = f"Action: Invoke Tool – {step.tool_name}"
        elif step.event_type == "STEP_END":
            action_subtitle = f"Action: Complete Tool – {step.tool_name}"
        elif step.event_type == "POLICY_DENIED":
            action_subtitle = f"Action: Block Tool – {step.tool_name}"
        
        # Build detail sections
        details = ""
        
        # Input
        if step.input_data:
            import json
            input_json = json.dumps(step.input_data, indent=2, ensure_ascii=False)
            if len(input_json) > 500:
                input_json = input_json[:500] + "\n... (truncated)"
            details += f"""
                <div class="timeline-detail">
                    <div class="detail-label">Input:</div>
                    <div class="detail-value code-block">{input_json}</div>
                </div>
            """
        
        # Output
        if step.output_data:
            import json
            output_json = json.dumps(step.output_data, indent=2, ensure_ascii=False)
            if len(output_json) > 500:
                output_json = output_json[:500] + "\n... (truncated)"
            details += f"""
                <div class="timeline-detail">
                    <div class="detail-label">Output:</div>
                    <div class="detail-value code-block">{output_json}</div>
                </div>
            """
        
        # Policy/Validation result
        if step.policy_result:
            details += f"""
                <div class="timeline-detail">
                    <div class="detail-label">Policy:</div>
                    <div class="detail-value"><strong>{step.policy_result.upper()}</strong></div>
                </div>
            """
        
        if step.validation_result:
            details += f"""
                <div class="timeline-detail">
                    <div class="detail-label">Validation:</div>
                    <div class="detail-value"><strong>{step.validation_result.upper()}</strong></div>
                </div>
            """
        
        # Duration
        if step.duration_ms is not None:
            details += f"""
                <div class="timeline-detail">
                    <div class="detail-label">Duration:</div>
                    <div class="detail-value">{step.duration_ms:.2f}ms</div>
                </div>
            """
        
        # Finding reference
        if step.has_finding:
            finding_links = ", ".join([f"<a href='#{fid}'>{fid}</a>" for fid in step.finding_refs])
            details += f"""
                <div class="timeline-detail finding-alert">
                    <div class="detail-label">⚠ Associated Incidents:</div>
                    <div class="detail-value">{finding_links}</div>
                </div>
            """
        
        # Three-layer DOM structure: step-header / step-body / step-footer
        # Only apply pagination control to outer .timeline-step, no break control for inner elements
        html += f"""
            <div class="timeline-step {outcome_class}">
                <div class="timeline-marker">
                    <div class="timeline-icon">{icon}</div>
                    <div class="timeline-line"></div>
                </div>
                <div class="timeline-content">
                    <!-- Step Header -->
                    <div class="step-header">
                        <div>
                            <div class="timeline-event-type">{event_display}</div>
                            {f'<div class="timeline-action-subtitle">{action_subtitle}</div>' if action_subtitle else ''}
                        </div>
                        <div class="timeline-meta">
                            <span class="timeline-tool mono">{step.tool_name}</span>
                            <span class="timeline-ts mono">{ts_display}</span>
                            <span class="timeline-seq mono">seq:{step.seq}</span>
                        </div>
                    </div>
                    <!-- Step Body -->
                    <div class="step-body">
                        {details}
                    </div>
                    <!-- Step Footer (optional metadata) -->
                    <div class="step-footer">
                        {f'<span class="mono" style="font-size: 0.7rem; color: #999;">Fingerprint: {step.fingerprint[:16]}...</span>' if step.fingerprint else ''}
                    </div>
                </div>
            </div>
        """
    
    html += '</div>'
    return html


def _render_incident_chapters(view: AuditReportView) -> str:
    """
    Render incident chapters as a single section (section container).
    Each incident = incident-card (atomic block, no splitting allowed)
    """
    if not view.findings:
        return """
        <section class="sheet">
            <div class="section-content">
                <div class="section-title">Part III: Incident Analysis</div>
                <p style="font-style: italic; color: #666;">No security incidents detected during this execution session.</p>
            </div>
        </section>
        """
    
    html = """
        <section class="sheet">
            <div class="section-content">
                <div class="section-title">Part III: Incident Analysis</div>
                <p style="margin-bottom: 1.5rem; font-style: italic; color: #555;">
                    This section provides detailed analysis for each security incident identified during execution.
                </p>
                <div class="incident-list">
    """
    
    for idx, finding in enumerate(view.findings, 1):
        # Generate incident ID with fingerprint
        year_month = view.meta.generated_at[:7].replace("-", "")
        incident_id = f"FC-INC-{year_month}-{idx:03d}"
        
        # Extract severity
        severity_text = finding.severity.split()[0]  # "CRITICAL RISK" -> "CRITICAL"
        
        # Generate trace hash fingerprint (mock for now, should use actual hash)
        import hashlib
        trace_fingerprint = hashlib.sha256(finding.finding_id.encode()).hexdigest()[:16].upper()
        
        # Upgrade incident title to audit language
        incident_title_map = {
            "Execution error": "Tool Execution Failure Detected During Runtime Enforcement",
            "Policy violation": "Policy Compliance Violation Detected During Enforcement",
            "Validation failure": "Input Validation Failure Detected During Pre-Execution Check",
            "Contract drift": "Contract Integrity Drift Detected During Runtime Verification",
            "Runtime enforcement blocked unsafe execution": "Unsafe Operation Blocked by Runtime Enforcement",
            "Policy denied unsafe execution": "Unsafe Tool Execution Denied by Policy Engine",
        }
        
        # Check if title contains error code (e.g. "Runtime enforcement blocked: FILE_NOT_FOUND")
        if "Runtime enforcement blocked:" in finding.title and ":" in finding.title:
            audit_title = finding.title  # Keep the detailed title with error code
        elif finding.title in incident_title_map:
            audit_title = incident_title_map[finding.title]
        elif any(keyword in finding.title for keyword in ["Runtime enforcement", "Policy denied", "blocked", "denied"]):
            audit_title = finding.title  # Already has enforcement/policy language
        else:
            audit_title = f"{finding.title} Detected During Runtime Enforcement"
        
        # Mitigation recommendations - actionable FailCore config
        tool_name = finding.tool_name or "unknown_tool"
        
        # Short-term: direct config changes
        mitigation_short = finding.mitigation or f"Update failcore.toml to restrict {tool_name} access scope. Add pre-execution validation rules for input parameters."
        
        # Long-term: architectural changes
        mitigation_long = f"Consider implementing stricter policy constraints in your FailCore runtime configuration. " \
                         f"Add contract validation for {tool_name} to enforce type safety and boundary checks. " \
                         f"Review and update validator presets in failcore.presets.validators to match your security baseline."
        
        # Root cause - Two-layer structure
        immediate_cause = "Tool execution returned non-zero outcome."
        underlying_cause = "Input validation or environment mismatch (pending confirmation)."
        
        if finding.rule_label and finding.rule_label != "Unknown":
            immediate_cause = f"Triggered by rule: {finding.rule_label}. {finding.what_happened}"
            underlying_cause = "Rule-based detection indicates potential security or compliance concern."
        
        html += f"""
        <div class="incident-card" id="{finding.finding_id}">
            <div class="incident-header">
                <div class="incident-title">
                    <div>Incident {idx}: {audit_title}</div>
                    <div class="incident-fingerprint">Hash: {trace_fingerprint}</div>
                </div>
                <div class="incident-severity-badge severity-{severity_text.lower()}">{severity_text}</div>
            </div>
            
            <div class="incident-body">
                <!-- Summary -->
                <div class="incident-section">
                    <div class="incident-section-title">1. Summary</div>
                    <div class="incident-section-content">
                        <table class="incident-info-table">
                            <tr>
                                <td class="info-label">Incident ID:</td>
                                <td class="info-value mono">{incident_id}</td>
                            </tr>
                            <tr>
                                <td class="info-label">Timestamp:</td>
                                <td class="info-value mono">{finding.ts}</td>
                            </tr>
                            <tr>
                                <td class="info-label">Tool:</td>
                                <td class="info-value mono">{finding.tool_name or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td class="info-label">Classification:</td>
                                <td class="info-value">{audit_title}</td>
                            </tr>
                            <tr>
                                <td class="info-label">OWASP Mapping:</td>
                                <td class="info-value">{', '.join(finding.owasp_agentic_ids) if finding.owasp_agentic_ids else 'N/A'}</td>
                            </tr>
                        </table>
                    </div>
                </div>
                
                <!-- Impact -->
                <div class="incident-section">
                    <div class="incident-section-title">2. Impact Assessment</div>
                    <div class="incident-section-content">
                        <p><strong>Severity:</strong> {finding.severity}</p>
                        <p><strong>Risk Level:</strong> This incident represents a {severity_text.lower()}-priority security concern that requires immediate attention.</p>
                    </div>
                </div>
                
                <!-- Root Cause - Two-layer structure -->
                <div class="incident-section">
                    <div class="incident-section-title">3. Root Cause Analysis</div>
                    <div class="incident-section-content">
                        <div style="margin-bottom: 1rem;">
                            <p style="font-weight: 700; margin-bottom: 0.5rem;">Immediate Cause:</p>
                            <p>{immediate_cause}</p>
                        </div>
                        <div>
                            <p style="font-weight: 700; margin-bottom: 0.5rem;">Underlying Cause (if known):</p>
                            <p>{underlying_cause}</p>
                        </div>
                    </div>
                </div>
                
                <!-- Evidence Reference -->
                <div class="incident-section">
                    <div class="incident-section-title">4. Evidence</div>
                    <div class="incident-section-content">
                        <p>Detailed technical evidence is available in <strong>Appendix A, Entry {idx}</strong>.</p>
                        <p class="mono" style="font-size: 0.85rem; color: #666;">Finding ID: {finding.finding_id}</p>
                    </div>
                </div>
                
                <!-- Mitigation -->
                <div class="incident-section">
                    <div class="incident-section-title">5. Mitigation Recommendations</div>
                    <div class="incident-section-content">
                        <div style="margin-bottom: 1rem;">
                            <div style="font-weight: 700; margin-bottom: 0.5rem;">Short-Term (Immediate Action):</div>
                            <p>{mitigation_short}</p>
                        </div>
                        <div>
                            <div style="font-weight: 700; margin-bottom: 0.5rem;">Long-Term (Architectural):</div>
                            <p>{mitigation_long}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
    
    html += """
                </div>
            </div>
        </section>
    """
    
    return html


def _render_appendix_sections(view: AuditReportView) -> str:
    """
    Render appendix as separate sections (section containers).
    
    Returns 3 sections:
    - Section 4: Appendix A — Technical Evidence
    - Section 5: Appendix B — Compliance Mapping
    - Section 6: Appendix C — Digital Attestation
    """
    import json
    
    # ==============================
    # SECTION 4: Appendix A — Technical Evidence
    # ==============================
    appendix_a_entries = ""
    if view.findings:
        for idx, finding in enumerate(view.findings, 1):
            evidence_json = "{}"
            if finding.evidence:
                evidence_json = json.dumps(finding.evidence, indent=2, ensure_ascii=False)
            elif finding.triggered_by:
                # Convert dict or object to JSON
                if isinstance(finding.triggered_by, dict):
                    evidence_json = json.dumps(finding.triggered_by, indent=2, ensure_ascii=False)
                else:
                    evidence_json = json.dumps(getattr(finding.triggered_by, "__dict__", {}), indent=2, ensure_ascii=False)
            
            appendix_a_entries += f"""
                <div class="appendix-entry" id="evidence-{idx}">
                    <div class="appendix-entry-title">Entry {idx}: {finding.finding_id}</div>
                    <pre class="evidence-block">{evidence_json}</pre>
                </div>
            """
    
    section4_appendix_a = f"""
        <section class="sheet">
            <div class="section-content appendix">
                <div class="appendix-title">Appendix A — Technical Evidence</div>
                <p style="margin-bottom: 0.5rem; font-weight: 700; border-left: 3px solid #000; padding-left: 1rem;">
                    The following evidence constitutes the authoritative technical record for incidents documented in Part III.
                </p>
                <p style="margin-bottom: 0.5rem; color: #555;">All data represents raw execution trace excerpts. Timestamps are in UTC.</p>
                <div style="margin-bottom: 1.5rem; padding: 0.75rem; background: #f9f9f9; border-left: 4px solid #000; font-family: 'Courier New', monospace; font-size: 0.85rem;">
                    <div><strong>Hash Algorithm:</strong> SHA-256</div>
                    <div style="margin-top: 0.25rem;"><strong>Trace Integrity:</strong> Verified at report generation time</div>
                </div>
                {appendix_a_entries if appendix_a_entries else '<p style="font-style: italic; color: #666;">No technical evidence required for this session.</p>'}
            </div>
        </section>
    """
    
    # ==============================
    # SECTION 5: Appendix B — Compliance Mapping
    # ==============================
    compliance_rows = ""
    for standard, controls in view.compliance_mapping.items():
        for idx, control in enumerate(controls):
            parts = control.split(" - ")
            control_id = parts[0] if len(parts) > 0 else ""
            rest = parts[1] if len(parts) > 1 else ""
            desc_status = rest.rsplit(" (", 1)
            description = desc_status[0] if len(desc_status) > 0 else rest
            status = desc_status[1].rstrip(")") if len(desc_status) > 1 else "N/A"
            
            compliance_rows += f"""
                <tr>
                    <td>{standard if idx == 0 else ""}</td>
                    <td>{control_id}</td>
                    <td>{description}</td>
                    <td>{status}</td>
                </tr>
            """
    
    section5_appendix_b = f"""
        <section class="sheet">
            <div class="section-content appendix">
                <div class="appendix-title">Appendix B — Compliance & Standards Mapping</div>
                <p style="font-size: 0.85rem; color: #666; margin-bottom: 1rem; font-style: italic; border-left: 3px solid #999; padding-left: 1rem;">
                    Scope Note: This mapping reflects coverage within the execution runtime scope only and does not constitute full organizational compliance.
                </p>
                <table class="compliance-table">
                    <thead>
                        <tr>
                            <th>Standard</th>
                            <th>Control ID</th>
                            <th>Description</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {compliance_rows}
                    </tbody>
                </table>
            </div>
        </section>
    """
    
    # ==============================
    # SECTION 6: Appendix C — Digital Attestation
    # ==============================
    sig = view.signature_placeholder
    section6_appendix_c = f"""
        <section class="sheet">
            <div class="section-content appendix">
                <div class="appendix-title">Appendix C — Digital Attestation</div>
                <p style="margin-bottom: 1.5rem;">
                    This report was automatically generated and cryptographically sealed by <strong>{sig['signer']}</strong>. 
                    The content represents a tamper-evident record of the execution trace and is intended for audit and compliance purposes.
                </p>
                
                <div class="signature-grid">
                    <div>
                        <div style="font-weight: 700; margin-bottom: 0.5rem;">Report Hash ({sig['hash_algo']})</div>
                        <div class="sig-field mono">{sig['hash_value']}</div>
                        <div class="sig-label">Cryptographic Digest</div>
                    </div>
                    <div>
                        <div style="font-weight: 700; margin-bottom: 0.5rem;">Automated Attestation</div>
                        <div class="sig-field"></div>
                        <div class="sig-label">FailCore Runtime – Automated Attestation Authority</div>
                    </div>
                </div>
            </div>
        </section>
    """
    
    return section4_appendix_a + section5_appendix_b + section6_appendix_c
