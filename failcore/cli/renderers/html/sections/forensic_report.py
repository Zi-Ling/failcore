# failcore/cli/renderers/html/sections/forensic_report.py
"""
Forensic Audit Report Renderer (Legal Document Format)
"""

from typing import List
from ....views.forensic_report import ForensicReportView, ForensicFindingView


def render_forensic_audit_section(view: ForensicReportView) -> str:
    """
    Render forensic audit report as a formal legal document.
    Structure: Executive Summary -> Scope -> Compliance -> Incidents -> Appendix -> Attestation
    """
    
    # Document Header (not HTML <header>, but document title block)
    doc_header = f"""
        <div class="doc-header">
            <div class="doc-title">FailCore Forensic Audit Report</div>
            <div class="doc-classification">CONFIDENTIAL</div>
            <div style="margin-top: 1rem; font-size: 0.85rem; line-height: 1.6; color: #333; border-left: 3px solid #000; padding-left: 1rem;">
                This document is an official forensic audit record.<br>
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
    
    # Section 1: Executive Summary
    # Extract conclusion (first sentence or two)
    exec_lines = view.executive_summary.split(". ")
    conclusion_line = exec_lines[0] + "." if exec_lines else view.executive_summary
    rest_summary = ". ".join(exec_lines[1:]) if len(exec_lines) > 1 else ""
    
    section_1 = f"""
        <div class="section">
            <div class="section-title">1. Executive Summary</div>
            <div class="section-content">
                <div class="exec-summary-box">
                    <div style="font-weight: 700; margin-bottom: 0.5rem;">Conclusion:</div>
                    <p>{conclusion_line}</p>
                    <p style="margin-top: 0.5rem;">{rest_summary}</p>
                </div>
                
                <div style="display: flex; gap: 2rem; margin-top: 1.5rem; justify-content: space-around;">
                    <div style="text-align: center;">
                        <div style="font-size: 0.75rem; color: #666; text-transform: uppercase; margin-bottom: 0.25rem;">Overall Risk</div>
                        <div style="font-size: 2rem; font-weight: 700;">{view.summary.risk_score}/100</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 0.75rem; color: #666; text-transform: uppercase; margin-bottom: 0.25rem;">Incidents</div>
                        <div style="font-size: 2rem; font-weight: 700;">{view.summary.findings_total}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 0.75rem; color: #666; text-transform: uppercase; margin-bottom: 0.25rem;">Blocks</div>
                        <div style="font-size: 2rem; font-weight: 700;">{view.value_metrics.policy_denied_findings}</div>
                    </div>
                </div>
            </div>
        </div>
    """
    
    # Section 2: Scope & Methodology
    section_2 = f"""
        <div class="section">
            <div class="section-title">2. Scope & Methodology</div>
            <div class="section-content">
                <p><strong>Audit Scope:</strong> This forensic audit covers the execution trace recorded during runtime session <span class="mono">{view.meta.run_id}</span>.</p>
                <p style="margin-top: 0.5rem;"><strong>Methodology:</strong> FailCore Runtime employs deterministic trace recording (schema {view.meta.trace_schema or 'v0.1.2'}) to capture all tool invocations, policy decisions, and execution outcomes. Analysis was performed using automated forensic rules against established security baselines.</p>
                <p style="margin-top: 0.5rem;"><strong>Source Trace:</strong> <span class="mono">{view.meta.trace_path or 'N/A'}</span></p>
            </div>
        </div>
    """
    
    # Section 3: Compliance & Standards Mapping (TABLE, NOT CARDS)
    compliance_rows = ""
    for standard, controls in view.compliance_mapping.items():
        for idx, control in enumerate(controls):
            # Parse "ID - Description (Status)" format
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
    
    section_3 = f"""
        <div class="section">
            <div class="section-title">3. Compliance & Standards Mapping</div>
            <div class="section-content">
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
        </div>
    """
    
    # Section 4: Incident Findings (NOT Web Cards, but Incident Records)
    incidents_html = ""
    if not view.findings:
        incidents_html = '<p style="font-style: italic; color: #666;">No anomalies detected during this session.</p>'
    else:
        for idx, finding in enumerate(view.findings, 1):
            # Generate incident number in legal format
            year_month = view.meta.generated_at[:7].replace("-", "")  # e.g., "202512"
            incident_id = f"FC-INC-{year_month}-{idx:03d}"
            
            # Severity mapping
            severity_text = finding.severity
            if "CRITICAL" in severity_text:
                severity_class = "CRITICAL"
            elif "HIGH" in severity_text:
                severity_class = "HIGH"
            elif "MEDIUM" in severity_text:
                severity_class = "MEDIUM"
            else:
                severity_class = "LOW"
            
            # Determination (not "violation" unless proven)
            determination = finding.what_happened
            if not determination.endswith("."):
                determination += "."
                
            incidents_html += f"""
                <div class="incident-record">
                    <div class="incident-header">
                        <div class="incident-id">Incident No.: {incident_id}</div>
                        <div class="severity-label">{severity_class}</div>
                    </div>
                    <div class="incident-body">
                        <div class="incident-field">
                            <span class="field-label">Classification:</span>
                            <div class="field-value">{finding.title}</div>
                        </div>
                        <div class="incident-field">
                            <span class="field-label">Timestamp:</span>
                            <div class="field-value mono">{finding.ts}</div>
                        </div>
                        <div class="incident-field">
                            <span class="field-label">Determination:</span>
                            <div class="field-value">{determination}</div>
                        </div>
                        <div class="incident-field">
                            <span class="field-label">Rule Reference:</span>
                            <div class="field-value mono">{finding.rule_id or 'N/A'}</div>
                        </div>
                        <div class="appendix-ref">
                            Technical Evidence: Refer to <strong>Appendix A, Entry {idx}</strong>
                        </div>
                    </div>
                </div>
            """
    
    section_4 = f"""
        <div class="section">
            <div class="section-title">4. Incident Findings</div>
            <div class="section-content">
                {incidents_html}
            </div>
        </div>
    """
    
    # Appendix A: Technical Evidence (Separate Section, not Toggle)
    appendix_entries = ""
    if view.findings:
        for idx, finding in enumerate(view.findings, 1):
            import json
            evidence_json = "{}"
            if finding.evidence:
                evidence_json = json.dumps(finding.evidence, indent=2, ensure_ascii=False)
            elif finding.triggered_by:
                evidence_json = json.dumps(finding.triggered_by, indent=2, ensure_ascii=False)
                
            appendix_entries += f"""
                <div style="margin-bottom: 2rem;">
                    <div style="font-weight: 700; margin-bottom: 0.5rem;">Entry {idx}: {finding.finding_id}</div>
                    <div class="evidence-block">{evidence_json}</div>
                </div>
            """
    
    appendix_a = f"""
        <div class="appendix-section">
            <div class="appendix-title">Appendix A — Technical Evidence</div>
            <div class="section-content">
                <p style="margin-bottom: 0.5rem; font-weight: 700; border-left: 3px solid #000; padding-left: 1rem;">
                    The following evidence constitutes the authoritative technical record for the incidents described above.
                </p>
                <p style="margin-bottom: 1rem;">All data represents raw execution trace excerpts. Timestamps are in UTC.</p>
                {appendix_entries if appendix_entries else '<p style="font-style: italic; color: #666;">No technical evidence required for this session.</p>'}
            </div>
        </div>
    """
    
    # Section 5: Digital Attestation
    sig = view.signature_placeholder
    section_5 = f"""
        <div class="signature-section">
            <div class="section-title">5. Digital Attestation</div>
            <div class="section-content">
                <p>This report was automatically generated and cryptographically sealed by <strong>{sig['signer']}</strong>. The content represents a tamper-evident record of the execution trace and is intended for audit and compliance purposes.</p>
                
                <div class="signature-grid">
                    <div>
                        <div style="font-weight: 700; margin-bottom: 0.5rem;">Report Hash ({sig['hash_algo']})</div>
                        <div class="sig-field mono">{sig['hash_value']}</div>
                        <div class="sig-label">Cryptographic Digest</div>
                    </div>
                    <div>
                        <div style="font-weight: 700; margin-bottom: 0.5rem;">Authorized Signature</div>
                        <div class="sig-field"></div>
                        <div class="sig-label">Chief Security Officer</div>
                    </div>
                </div>
            </div>
        </div>
    """
    
    return f"""
        {doc_header}
        {section_1}
        {section_2}
        {section_3}
        {section_4}
        {appendix_a}
        {section_5}
    """


# Backward compatibility placeholder
def render_forensic_section(*args, **kwargs):
    return ""
