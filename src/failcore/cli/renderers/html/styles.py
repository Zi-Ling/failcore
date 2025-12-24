# failcore/cli/renderers/html/styles.py
"""
CSS and JavaScript resources for HTML reports
"""


def get_css() -> str:
    """Get CSS styles for the HTML report"""
    return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.5;
            color: #1f2937;
            background: #f9fafb;
            padding: 2rem;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem 2.5rem;
        }
        
        .header h1 {
            font-size: 1.875rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .header-info {
            display: flex;
            gap: 2rem;
            margin-top: 1rem;
            font-size: 0.875rem;
            opacity: 0.95;
        }
        
        .header-info-item {
            display: flex;
            flex-direction: column;
        }
        
        .header-info-label {
            opacity: 0.8;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .header-info-value {
            font-weight: 600;
            margin-top: 0.25rem;
        }
        
        /* Section */
        .section {
            padding: 2rem 2.5rem;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .section:last-child {
            border-bottom: none;
        }
        
        .section h2 {
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            color: #111827;
        }
        
        /* Summary */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.5rem;
        }
        
        .summary-card {
            background: #f9fafb;
            border-radius: 8px;
            padding: 1.25rem;
            border: 1px solid #e5e7eb;
        }
        
        .summary-card-label {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b7280;
            margin-bottom: 0.5rem;
        }
        
        .summary-card-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #111827;
        }
        
        .summary-card-detail {
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 0.25rem;
        }
        
        /* Value proposition */
        .value-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        
        .value-list li {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            font-size: 0.9375rem;
        }
        
        .value-list li::before {
            content: "✓";
            color: #10b981;
            font-weight: 700;
            font-size: 1.125rem;
            flex-shrink: 0;
        }
        
        .value-list li.impact-warning::before {
            content: "";
        }
        
        /* Timeline */
        .timeline {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .timeline-item {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .timeline-item:hover {
            border-color: #d1d5db;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        
        /* Critical step highlighting - security events */
        .timeline-item.critical {
            border-left: 4px solid #ef4444;
            background: #fef2f2;
        }
        
        .timeline-item.critical:hover {
            border-color: #dc2626;
            box-shadow: 0 4px 8px rgba(239, 68, 68, 0.15);
        }
        
        /* Normal steps - de-emphasized */
        .timeline-item.normal {
            opacity: 0.85;
        }
        
        .timeline-item.normal:hover {
            opacity: 1;
        }
        
        .timeline-row {
            display: grid;
            grid-template-columns: 100px 1fr 100px 80px 2fr;
            gap: 1rem;
            padding: 0.875rem 1.25rem;
            align-items: center;
            font-size: 0.875rem;
        }
        
        .timeline-step-id {
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-weight: 600;
            color: #6b7280;
        }
        
        .timeline-tool {
            font-weight: 500;
            color: #111827;
        }
        
        .timeline-status {
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
        }
        
        .replay-badge {
            background: #3b82f6;
            color: white;
            padding: 0.125rem 0.5rem;
            border-radius: 3px;
            font-size: 0.625rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            white-space: nowrap;
        }
        
        .timeline-duration {
            color: #6b7280;
            text-align: right;
        }
        
        .timeline-params {
            color: #6b7280;
            font-size: 0.8125rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            word-break: break-all;
        }
        
        /* Step details */
        .step-details {
            display: none;
            background: #f9fafb;
            padding: 1.25rem;
            border-top: 1px solid #e5e7eb;
        }
        
        .step-details.expanded {
            display: block;
        }
        
        .detail-section {
            margin-bottom: 1rem;
        }
        
        .detail-section:last-child {
            margin-bottom: 0;
        }
        
        .detail-label {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b7280;
            margin-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .copy-btn {
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
        }
        
        .copy-btn:hover {
            background: #2563eb;
        }
        
        .copy-btn:active {
            background: #1d4ed8;
        }
        
        .copy-btn.copied {
            background: #10b981;
        }
        
        .detail-code {
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 0.8125rem;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            padding: 0.75rem;
            overflow-x: auto;
            color: #111827;
            white-space: pre-wrap;
            word-break: break-word;
        }
        
        /* Simple JSON syntax highlighting */
        .detail-code .json-key {
            color: #0369a1;
            font-weight: 600;
        }
        
        .detail-code .json-string {
            color: #15803d;
        }
        
        .detail-code .json-number {
            color: #b45309;
        }
        
        .detail-code .json-boolean {
            color: #7c2d12;
            font-weight: 600;
        }
        
        .detail-code .json-null {
            color: #6b7280;
            font-weight: 600;
        }
        
        .detail-code.error {
            color: #dc2626;
            border-color: #fecaca;
            background: #fef2f2;
        }
        
        .event-tag {
            display: inline-block;
            padding: 0.25rem 0.625rem;
            background: #dbeafe;
            color: #1e40af;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-right: 0.5rem;
        }
        
        .event-tag-warning {
            background: #fef3c7;
            color: #92400e;
        }
        
        .warning-indicator {
            font-size: 0.875rem;
        }
        
        .warning-text {
            color: #f59e0b;
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        /* v0.1.2: Metadata badges */
        .metadata-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .metadata-badge {
            display: inline-block;
            padding: 0.375rem 0.75rem;
            background: #e5e7eb;
            color: #374151;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .provenance-badge {
            background: #dbeafe;
            color: #1e40af;
            padding: 0.125rem 0.5rem;
            border-radius: 3px;
            font-size: 0.625rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-left: 0.5rem;
        }
        
        /* Failure detail */
        .failure-detail {
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 6px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }
        
        .failure-detail:last-child {
            margin-bottom: 0;
        }
        
        .failure-item {
            margin-bottom: 1rem;
        }
        
        .failure-item:last-child {
            margin-bottom: 0;
        }
        
        .failure-field {
            margin-bottom: 0.5rem;
            font-size: 0.9375rem;
        }
        
        /* Warning detail */
        .warning-detail {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-radius: 6px;
            padding: 1.25rem;
        }
        
        .warning-item {
            margin-bottom: 1rem;
        }
        
        .warning-item:last-child {
            margin-bottom: 0;
        }
        
        .detail-subtitle {
            font-size: 0.875rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #374151;
            margin-bottom: 1rem;
        }
        
        /* v0.1.2: Security violation forensic view */
        .security-violation {
            background: linear-gradient(135deg, #fef2f2 0%, #fff5f5 100%);
            border-left: 4px solid #dc2626;
        }
        
        .failure-header {
            font-size: 0.9375rem;
            font-weight: 700;
            color: #991b1b;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #fecaca;
        }
        
        .violation-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        
        .violation-field {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        
        .violation-label {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b7280;
        }
        
        .violation-code {
            font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
            font-size: 0.8125rem;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            padding: 0.375rem 0.5rem;
            color: #111827;
            word-break: break-all;
            white-space: pre-wrap;
            overflow-wrap: break-word;
        }
        
        .violation-code.danger {
            background: #fef2f2;
            border-color: #fecaca;
            color: #dc2626;
            font-weight: 600;
        }
        
        .violation-explanation {
            background: white;
            border: 1px solid #fecaca;
            border-radius: 4px;
            padding: 0.75rem;
            margin-bottom: 0.75rem;
            font-size: 0.875rem;
            color: #374151;
        }
        
        .violation-suggestion {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-radius: 4px;
            padding: 0.75rem;
            font-size: 0.875rem;
            color: #78350f;
        }
        
        .violation-suggestion strong {
            color: #92400e;
        }
        
        .threat-classification {
            background: #fff7ed;
            border: 1px solid #fed7aa;
            border-radius: 4px;
            padding: 0.5rem 0.75rem;
            margin-bottom: 1rem;
            font-size: 0.875rem;
        }
        
        .threat-class-label {
            font-weight: 600;
            color: #9a3412;
            margin-right: 0.5rem;
        }
        
        .threat-class-value {
            color: #c2410c;
            font-weight: 500;
        }
        
        /* Forensic Analysis Three-Part Structure */
        .forensic-violation-section,
        .forensic-impact-section,
        .forensic-resolution-section {
            margin-bottom: 1rem;
            border-radius: 4px;
            padding: 0.75rem;
        }
        
        .forensic-violation-section {
            background: #fef3c7;
            border: 1px solid #fcd34d;
        }
        
        .forensic-impact-section {
            background: #fee2e2;
            border: 1px solid #fecaca;
        }
        
        .forensic-resolution-section {
            background: #dcfce7;
            border: 1px solid #86efac;
        }
        
        .forensic-section-title {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        
        .forensic-violation-section .forensic-section-title {
            color: #92400e;
        }
        
        .forensic-impact-section .forensic-section-title {
            color: #991b1b;
        }
        
        .forensic-resolution-section .forensic-section-title {
            color: #166534;
        }
        
        .forensic-section-content {
            font-size: 0.875rem;
            line-height: 1.6;
            color: #374151;
        }
        
        /* Footer */
        .footer {
            padding: 1.5rem 2.5rem;
            background: #f9fafb;
            border-top: 1px solid #e5e7eb;
            font-size: 0.8125rem;
            color: #6b7280;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .footer-item {
            display: flex;
            flex-direction: column;
        }
        
        .footer-label {
            font-weight: 600;
            color: #9ca3af;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .footer-value {
            color: #4b5563;
            margin-top: 0.25rem;
        }
    """


def get_javascript() -> str:
    """Get JavaScript code for the HTML report"""
    return """
        function toggleDetails(stepId) {
            const details = document.getElementById('details-' + stepId);
            if (details.classList.contains('expanded')) {
                details.classList.remove('expanded');
            } else {
                // Close other expanded items
                document.querySelectorAll('.step-details.expanded').forEach(el => {
                    el.classList.remove('expanded');
                });
                details.classList.add('expanded');
            }
        }
        
        function copyToClipboard(elementId, event) {
            event.stopPropagation(); // Prevent toggle
            
            const element = document.getElementById(elementId);
            const button = event.target;
            
            if (!element) return;
            
            // Get text content
            const text = element.textContent || element.innerText;
            
            // Copy to clipboard
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => {
                    // Visual feedback
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    button.classList.add('copied');
                    
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.classList.remove('copied');
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy:', err);
                    alert('Failed to copy to clipboard');
                });
            } else {
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                
                try {
                    document.execCommand('copy');
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    button.classList.add('copied');
                    
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy:', err);
                    alert('Failed to copy to clipboard');
                } finally {
                    document.body.removeChild(textarea);
                }
            }
        }
    """

