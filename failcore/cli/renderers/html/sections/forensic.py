# failcore/cli/renderers/html/sections/forensic.py
"""
Forensic analysis section renderer - Threat and warning details
"""

import re
from typing import List
from ....views.trace_report import ReportStepView


def render_forensic_section(failures: List[ReportStepView], warnings: List[ReportStepView], sandbox_root: str = ".failcore/sandbox") -> str:
    """Render forensic analysis section with failures and warnings"""
    if not failures and not warnings:
        return ""
    
    sections_html = ""
    
    # Render failures with specialized forensic components
    if failures:
        failure_items = ""
        for failure in failures:
            # Determine threat category
            is_security_threat = failure.phase in ("validate", "policy")
            threat_icon = "🛡️" if is_security_threat else "⚠️"
            threat_category = "SECURITY THREAT" if is_security_threat else "EXECUTION ERROR"
            
            # Render specialized component based on error code
            if failure.error_code in ("PATH_TRAVERSAL", "SANDBOX_VIOLATION"):
                failure_items += _render_path_security_violation(failure, threat_icon, sandbox_root)
            elif failure.error_code in ("SSRF_BLOCKED", "DOMAIN_NOT_ALLOWED", "PORT_NOT_ALLOWED"):
                failure_items += _render_network_security_violation(failure, threat_icon)
            else:
                # Generic failure rendering
                failure_items += _render_generic_failure(failure, threat_icon, threat_category)
        
        sections_html += f"""
            <div class="failure-detail">
                <div class="detail-subtitle">🔍 Threat Analysis</div>
                {failure_items}
            </div>
        """
    
    # Render warnings
    if warnings:
        warning_items = ""
        for warning in warnings:
            warning_items += _render_warning_item(warning)
        
        sections_html += f"""
            <div class="warning-detail">
                <div class="detail-subtitle">Warnings</div>
                {warning_items}
            </div>
        """
    
    return f"""
        <section class="section">
            <h2>🔍 Forensic Analysis</h2>
            {sections_html}
        </section>
    """


def _render_generic_failure(failure: ReportStepView, threat_icon: str, threat_category: str) -> str:
    """Render a generic failure item"""
    failure_detail = f"<strong>Message:</strong> {failure.error_message}"
    if failure.rule_id:
        failure_detail = f"<strong>Policy:</strong> {failure.policy_id or 'N/A'} / {failure.rule_id}<br>{failure_detail}"
    
    return f"""
        <div class="failure-item">
            <div class="failure-header">{threat_icon} <strong>{threat_category}</strong></div>
            <div class="failure-field"><strong>Step:</strong> {failure.step_id}</div>
            <div class="failure-field"><strong>Error Code:</strong> {failure.error_code}</div>
            <div class="failure-field">{failure_detail}</div>
        </div>
    """


def _render_path_security_violation(failure: ReportStepView, threat_icon: str, sandbox_root: str = ".failcore/sandbox") -> str:
    """Render specialized component for path security violations"""
    # Extract path details from error message
    error_msg = failure.error_message or ""
    
    # Try to extract paths from message
    path_match = re.search(r"'([^']+)'", error_msg)
    attempted_path = path_match.group(1) if path_match else "N/A"
    
    # Determine threat classification and impact
    if failure.error_code == "PATH_TRAVERSAL":
        threat_type = "Path Traversal Attack"
        threat_class = "Directory Escape Attempt"
        violation_desc = "Attempted to escape sandbox using '../' path components"
        impact_desc = "If not blocked, this operation would have allowed the tool to access arbitrary files on the host system, potentially reading sensitive data or overwriting critical files."
        resolution_desc = "FailCore detected the path traversal pattern and blocked execution before any file operation occurred. The sandbox boundary was preserved."
    else:
        threat_type = "Sandbox Boundary Violation"
        threat_class = "Unauthorized Path Access"
        violation_desc = "Attempted to access file outside sandbox root using absolute path"
        impact_desc = "If not blocked, this operation would have allowed direct access to files outside the designated sandbox, bypassing the containment policy."
        resolution_desc = "FailCore validated the path against the sandbox root and rejected the operation. No files were accessed or modified."
    
    # Generate actionable fix code
    fix_code = f'# Use relative path within sandbox\npath = "{sandbox_root}/important_data.txt"'
    
    return f"""
        <div class="failure-item security-violation">
            <div class="failure-header">{threat_icon} <strong>SECURITY THREAT: {threat_type}</strong></div>
            <div class="threat-classification">
                <span class="threat-class-label">Threat Class:</span>
                <span class="threat-class-value">{threat_class}</span>
            </div>
            <div class="violation-grid">
                <div class="violation-field">
                    <span class="violation-label">Attempted Path:</span>
                    <code class="violation-code danger">{attempted_path}</code>
                </div>
                <div class="violation-field">
                    <span class="violation-label">Sandbox Root:</span>
                    <code class="violation-code">{sandbox_root}</code>
                </div>
                <div class="violation-field">
                    <span class="violation-label">Step ID:</span>
                    <code class="violation-code">{failure.step_id}</code>
                </div>
                <div class="violation-field">
                    <span class="violation-label">Tool:</span>
                    <code class="violation-code">{failure.tool}</code>
                </div>
                <div class="violation-field">
                    <span class="violation-label">Threat Code:</span>
                    <code class="violation-code">{failure.error_code}</code>
                </div>
            </div>
            
            <div class="forensic-violation-section">
                <div class="forensic-section-title">📋 VIOLATION</div>
                <div class="forensic-section-content">{violation_desc}</div>
            </div>
            
            <div class="forensic-impact-section">
                <div class="forensic-section-title">⚠️ POTENTIAL IMPACT</div>
                <div class="forensic-section-content">{impact_desc}</div>
            </div>
            
            <div class="forensic-resolution-section">
                <div class="forensic-section-title">✅ RESOLUTION</div>
                <div class="forensic-section-content">{resolution_desc}</div>
            </div>
            
            <div class="violation-suggestion">
                <strong>💡 Suggested Fix:</strong>
                <div style="margin-top: 0.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                        <span style="font-size: 0.75rem; color: #78350f;">Minimal fix example:</span>
                        <button class="copy-btn" onclick="copyToClipboard('fix-{failure.step_id}', event)" style="font-size: 0.625rem; padding: 0.125rem 0.375rem;">Copy</button>
                    </div>
                    <pre id="fix-{failure.step_id}" style="background: white; border: 1px solid #fcd34d; border-radius: 3px; padding: 0.5rem; font-size: 0.75rem; margin: 0; overflow-x: auto;">{fix_code}</pre>
                </div>
            </div>
        </div>
    """


def _render_network_security_violation(failure: ReportStepView, threat_icon: str) -> str:
    """Render specialized component for network security violations"""
    error_msg = failure.error_message or ""
    
    # Determine threat classification with impact analysis
    threat_map = {
        "SSRF_BLOCKED": {
            "type": "SSRF Attack Blocked",
            "class": "Internal Network Access Attempt",
            "violation": "Attempted to send HTTP request to internal/private network address",
            "impact": "If not blocked, this request could have exposed internal services, cloud metadata endpoints (AWS/GCP), or private network resources to unauthorized access.",
            "resolution": "FailCore's SSRF protection detected the internal IP address and blocked the request before any network connection was established."
        },
        "DOMAIN_NOT_ALLOWED": {
            "type": "Unauthorized Domain Access",
            "class": "Domain Allowlist Violation",
            "violation": "Attempted to connect to a domain not present in the allowlist",
            "impact": "If not blocked, this could have resulted in data exfiltration, communication with malicious C&C servers, or unintended API calls to unauthorized services.",
            "resolution": "FailCore enforced the domain allowlist policy and rejected the connection. No external network request was made."
        },
        "PORT_NOT_ALLOWED": {
            "type": "Unauthorized Port Access",
            "class": "Port Restriction Violation",
            "violation": "Attempted to connect using a non-standard port",
            "impact": "If not blocked, this could have enabled access to non-HTTP services, database servers, or administrative interfaces not intended for tool access.",
            "resolution": "FailCore validated the port against the allowed list and blocked the connection attempt."
        },
    }
    threat_info = threat_map.get(failure.error_code, {
        "type": "Network Security Violation",
        "class": "Network Access Violation",
        "violation": "Network access violation detected",
        "impact": "Potential unauthorized network access was prevented.",
        "resolution": "FailCore blocked the operation based on network security policy."
    })
    
    # Extract URL/domain from message
    url_match = re.search(r"'([^']+)'|: ([^\s]+)", error_msg)
    target = url_match.group(1) or url_match.group(2) if url_match else "N/A"
    
    # Generate actionable fix code
    fix_code = f'# Add to network allowlist\nsession.register(\n    "http_request",\n    fn,\n    network_allowlist=["api.example.com"]\n)'
    
    return f"""
        <div class="failure-item security-violation">
            <div class="failure-header">{threat_icon} <strong>SECURITY THREAT: {threat_info['type']}</strong></div>
            <div class="threat-classification">
                <span class="threat-class-label">Threat Class:</span>
                <span class="threat-class-value">{threat_info['class']}</span>
            </div>
            <div class="violation-grid">
                <div class="violation-field">
                    <span class="violation-label">Target:</span>
                    <code class="violation-code danger">{target}</code>
                </div>
                <div class="violation-field">
                    <span class="violation-label">Step ID:</span>
                    <code class="violation-code">{failure.step_id}</code>
                </div>
                <div class="violation-field">
                    <span class="violation-label">Tool:</span>
                    <code class="violation-code">{failure.tool}</code>
                </div>
                <div class="violation-field">
                    <span class="violation-label">Threat Code:</span>
                    <code class="violation-code">{failure.error_code}</code>
                </div>
            </div>
            
            <div class="forensic-violation-section">
                <div class="forensic-section-title">📋 VIOLATION</div>
                <div class="forensic-section-content">{threat_info['violation']}</div>
            </div>
            
            <div class="forensic-impact-section">
                <div class="forensic-section-title">⚠️ POTENTIAL IMPACT</div>
                <div class="forensic-section-content">{threat_info['impact']}</div>
            </div>
            
            <div class="forensic-resolution-section">
                <div class="forensic-section-title">✅ RESOLUTION</div>
                <div class="forensic-section-content">{threat_info['resolution']}</div>
            </div>
            
            <div class="violation-suggestion">
                <strong>💡 Suggested Fix:</strong>
                <div style="margin-top: 0.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                        <span style="font-size: 0.75rem; color: #78350f;">Add to allowlist:</span>
                        <button class="copy-btn" onclick="copyToClipboard('fix-{failure.step_id}', event)" style="font-size: 0.625rem; padding: 0.125rem 0.375rem;">Copy</button>
                    </div>
                    <pre id="fix-{failure.step_id}" style="background: white; border: 1px solid #fcd34d; border-radius: 3px; padding: 0.5rem; font-size: 0.75rem; margin: 0; overflow-x: auto;">{fix_code}</pre>
                </div>
            </div>
        </div>
    """


def _render_warning_item(warning: ReportStepView) -> str:
    """Render a warning item"""
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
    
    return f"""
        <div class="warning-item">
            <div class="failure-field"><strong>Step:</strong> {warning.step_id}</div>
            <div class="failure-field"><strong>Type:</strong> {warning_type}</div>
            <div class="failure-field">{warning_detail}</div>
        </div>
    """

