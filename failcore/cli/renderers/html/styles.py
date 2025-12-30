# failcore/cli/renderers/html/styles.py
"""
CSS for Audit Report - Unified Screen + Print Style
One stylesheet for both screen preview and print output.
"""

def get_css() -> str:
    """
    Get CSS styles for Audit report.
    One stylesheet for both screen preview and print output - WYSIWYG.
    """
    return """
        /* ==========================================
           CSS Variables
           ========================================== */
        :root {
            --a4-w: 210mm;
            --a4-h: 297mm;
            --page-gap: 20px;
            --page-pad: 20mm;
            --print-margin: 16mm;
        }
        
        /* ==========================================
           SCREEN: Simulated PDF viewer
           ========================================== */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            margin: 0;
            background: #f0f2f5;
            font-family: Georgia, "Times New Roman", serif;
            line-height: 1.6;
            color: #1a1a1a;
        }
        
        .mode-preview {
            padding: 40px 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: var(--page-gap);
        }
        
        /* Section "paper container" (section container, not page container, allows variable length) */
        .mode-preview .sheet {
            width: var(--a4-w);
            min-height: var(--a4-h);
            background: #fff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.10);
            box-sizing: border-box;
            position: relative;
        }
        
        /* Content padding: screen uses padding; print delegates page margins to @page */
        .mode-preview .section-content {
            padding: var(--page-pad);
            box-sizing: border-box;
        }
        
        /* Screen only: section end marker with page counter */
        .mode-preview .sheet::after {
            content: "FAILCORE REPORT | SECTION " counter(sheet-counter) " | END";
            position: absolute;
            right: var(--page-pad);
            bottom: 10px;
            font-size: 10px;
            color: #c9cdd4;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        
        /* Sheet counter */
        .mode-preview {
            counter-reset: sheet-counter;
        }
        
        .mode-preview .sheet {
            counter-increment: sheet-counter;
        }
        
        /* ==========================================
           Atomic blocks prevent splitting (also used in print)
           ========================================== */
        .step,
        .incident-card,
        .appendix-entry {
            break-inside: avoid;
            page-break-inside: avoid;
            margin-bottom: 16px;
        }
        
        /* Code/JSON does not break page layout */
        pre, code, .evidence-block, .code-block {
            white-space: pre-wrap !important;
            word-break: break-all !important;
            overflow-wrap: anywhere !important;
        }
        
        /* ==========================================
           PRINT: Actual audit delivery format
           ========================================== */
        @media print {
            @page {
                size: A4;
                margin: var(--print-margin);
                @bottom-center {
                    content: "FailCore Verified – Hash-based Integrity | Page " counter(page) " of " counter(pages);
                    font-size: 9pt;
                    color: #666;
                }
            }
            
            body {
                background: #fff;
            }
            
            .mode-preview {
                padding: 0;
                gap: 0;
                display: block !important;  /* Disable flex to avoid pagination rule failure */
            }
            
            .sheet {
                width: auto;
                min-height: auto;
                box-shadow: none;
                display: block !important;
            }
            
            /* In print, no screen padding needed, page margins delegated to @page */
            .section-content {
                padding: 0;
            }
            
            /* Section pagination anchor: start new page from "section start" */
            .sheet {
                break-before: page;
                page-break-before: always;
            }
            .sheet:first-child {
                break-before: auto;
                page-break-before: auto;
            }
            
            /* Screen section end marker not printed */
            .mode-preview .sheet::after {
                content: none;
            }
            
            /* Prevent parent container layout from swallowing break-inside */
            .timeline, .incident-list, .appendix {
                display: block !important;
            }
            
            /* Force each Incident to start on a new page */
            .incident-card {
                break-before: page;
                page-break-before: always;
            }
        }
        
        /* ==========================================
           Common component styles (Screen + Print)
           ========================================== */
        
        /* Document Header */
        .doc-header {
            margin-bottom: 2rem;
            border-bottom: 4px double #000;
            padding-bottom: 1.5rem;
        }
        
        .doc-title {
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .doc-classification {
            display: inline-block;
            border: 2px solid #000;
            padding: 0.25rem 1rem;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            margin-top: 0.5rem;
        }
        
        .doc-metadata {
            margin-top: 1.5rem;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
            font-size: 0.85rem;
            font-family: "Courier New", monospace;
        }
        
        .metadata-row {
            display: flex;
        }
        
        .metadata-label {
            font-weight: 700;
            min-width: 120px;
        }
        
        .metadata-value {
            color: #333;
        }
        
        /* Section Title */
        .section-title {
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid #000;
            font-family: Georgia, serif;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Executive Summary Box */
        .exec-summary-box {
            padding: 1rem 1.5rem;
            background: #f9f9f9;
            border-left: 4px solid #000;
            margin-bottom: 1.5rem;
        }
        
        /* Risk Overview Grid */
        .risk-overview-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.5rem;
            margin: 1.5rem 0;
        }
        
        .risk-metric {
            text-align: center;
            padding: 1rem;
            border: 1px solid #ddd;
            background: #fafafa;
        }
        
        .metric-label {
            font-size: 0.75rem;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
            font-weight: 600;
            letter-spacing: 0.05em;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #000;
        }
        
        /* Risk Breakdown Table */
        .risk-breakdown-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.9rem;
        }
        
        .risk-breakdown-table th {
            background: #000;
            color: white;
            border: 1px solid #000;
            padding: 0.5rem;
            text-align: left;
            font-weight: 700;
        }
        
        .risk-breakdown-table td {
            border: 1px solid #ccc;
            padding: 0.5rem;
            font-family: "Courier New", monospace;
        }
        
        .risk-breakdown-table tr:nth-child(even) {
            background: #fafafa;
        }
        
        /* Compliance Table */
        .compliance-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.85rem;
        }
        
        .compliance-table th {
            background: #f0f0f0;
            border: 1px solid #000;
            padding: 0.5rem;
            text-align: left;
            font-weight: 700;
            font-family: Georgia, serif;
        }
        
        .compliance-table td {
            border: 1px solid #ccc;
            padding: 0.5rem;
            font-family: "Courier New", monospace;
            font-size: 0.8rem;
        }
        
        .compliance-table tr:nth-child(even) {
            background: #fafafa;
        }
        
        /* ==========================================
           Timeline Styles (Vertical)
           ========================================== */
        
        .timeline-container {
            position: relative;
            padding-left: 2rem;
            margin: 2rem 0;
        }
        
        .timeline-step {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            position: relative;
        }
        
        /* Tighter spacing for paired STEP_START/STEP_END */
        .timeline-step.outcome-ok + .timeline-step {
            margin-top: -0.3rem;
        }
        
        /* Three-layer DOM: step-header, step-body, step-footer */
        .step-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #ddd;
        }
        
        .step-body {
            /* Main content area */
        }
        
        .step-footer {
            margin-top: 0.5rem;
            padding-top: 0.5rem;
            border-top: 1px solid #e5e7eb;
            font-size: 0.7rem;
            color: #999;
        }
        
        .timeline-marker {
            display: flex;
            flex-direction: column;
            align-items: center;
            flex-shrink: 0;
        }
        
        .timeline-icon {
            width: 2rem;
            height: 2rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1rem;
            border: 2px solid;
            background: white;
            z-index: 2;
        }
        
        .timeline-line {
            width: 2px;
            flex-grow: 1;
            background: #ddd;
            margin-top: 0.25rem;
        }
        
        /* Outcome-based coloring */
        .outcome-ok .timeline-icon {
            border-color: #22c55e;
            color: #22c55e;
        }
        
        .outcome-denied .timeline-icon {
            border-color: #ef4444;
            color: #ef4444;
            background: #fee;
        }
        
        .outcome-failed .timeline-icon {
            border-color: #dc2626;
            color: #dc2626;
            background: #fee;
        }
        
        .outcome-warning .timeline-icon {
            border-color: #f59e0b;
            color: #f59e0b;
            background: #fffbeb;
        }
        
        .timeline-content {
            flex-grow: 1;
            border: 1px solid #e5e7eb;
            padding: 1rem;
            background: #fafafa;
            border-radius: 4px;
        }
        
        .timeline-event-type {
            font-weight: 700;
            font-size: 0.95rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .timeline-action-subtitle {
            font-size: 0.75rem;
            color: #777;
            margin-top: 0.25rem;
            font-style: italic;
            font-weight: 400;
            text-transform: none;
        }
        
        .timeline-action-subtitle {
            font-size: 0.75rem;
            color: #666;
            font-weight: 400;
            margin-top: 0.25rem;
            font-style: italic;
        }
        
        .timeline-meta {
            display: flex;
            gap: 1rem;
            font-size: 0.75rem;
            color: #666;
        }
        
        .timeline-tool {
            font-weight: 600;
        }
        
        .timeline-ts, .timeline-seq {
            color: #999;
        }
        
        .timeline-detail {
            margin-top: 0.75rem;
        }
        
        .detail-label {
            font-weight: 700;
            font-size: 0.8rem;
            text-transform: uppercase;
            color: #555;
            margin-bottom: 0.25rem;
        }
        
        .detail-value {
            margin-left: 0.5rem;
            color: #333;
        }
        
        .finding-alert {
            background: #fffbeb;
            border-left: 3px solid #f59e0b;
            padding: 0.5rem;
            margin-top: 0.75rem;
        }
        
        .finding-alert .detail-label {
            color: #f59e0b;
        }
        
        /* ==========================================
           Incident Card Styles
           ========================================== */
        
        .incident-card {
            margin-bottom: 2rem;
            border: 2px solid #000;
        }
        
        .incident-header {
            background: #000;
            color: white;
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .incident-title {
            flex-grow: 1;
        }
        
        .incident-title > div:first-child {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        
        .incident-fingerprint {
            font-family: "Courier New", monospace;
            font-size: 0.75rem;
            opacity: 0.8;
        }
        
        .incident-severity-badge {
            padding: 0.5rem 1rem;
            font-weight: 700;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            border: 2px solid white;
        }
        
        .severity-critical {
            background: #dc2626;
        }
        
        .severity-high {
            background: #f59e0b;
        }
        
        .severity-medium {
            background: #3b82f6;
        }
        
        .severity-low {
            background: #6b7280;
        }
        
        .incident-body {
            padding: 1.5rem;
            background: white;
        }
        
        .incident-section {
            margin-bottom: 1.5rem;
        }
        
        .incident-section-title {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid #ddd;
            padding-bottom: 0.5rem;
        }
        
        .incident-section-content {
            font-size: 0.9rem;
            line-height: 1.7;
        }
        
        .incident-info-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        
        .incident-info-table td {
            padding: 0.5rem;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .info-label {
            font-weight: 700;
            width: 180px;
            color: #555;
        }
        
        .info-value {
            color: #000;
        }
        
        /* ==========================================
           Appendix Styles
           ========================================== */
        
        .appendix-title {
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid #000;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .appendix-entry {
            margin-bottom: 2.5rem;
        }
        
        .appendix-entry-title {
            font-weight: 700;
            font-size: 0.95rem;
            margin-bottom: 0.75rem;
            padding: 0.5rem 1rem;
            background: #f0f0f0;
            border-left: 4px solid #000;
        }
        
        .evidence-block {
            background: #f9f9f9;
            border: 1px solid #ccc;
            padding: 1rem;
            font-family: "Courier New", monospace;
            font-size: 0.75rem;
            line-height: 1.4;
            max-width: 100%;
            /* Allow internal pagination for long JSON */
            break-inside: auto;
            page-break-inside: auto;
        }
        
        /* Continuation marker for paginated evidence */
        .evidence-block::after {
            content: "";
            display: block;
        }
        
        @media print {
            .evidence-block {
                orphans: 3;
                widows: 3;
            }
        }
        
        .code-block {
            background: #f5f5f5;
            border: 1px solid #ddd;
            padding: 0.75rem;
            font-family: "Courier New", monospace;
            font-size: 0.7rem;
            line-height: 1.4;
            border-radius: 3px;
            max-width: 100%;
        }
        
        /* Signature Section */
        .signature-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-top: 2rem;
        }
        
        .sig-field {
            border-bottom: 1px solid #000;
            padding-top: 3rem;
            padding-bottom: 0.5rem;
        }
        
        .sig-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #666;
            margin-top: 0.25rem;
        }
        
        /* ==========================================
           Utility Classes
           ========================================== */
        
        .mono {
            font-family: "Courier New", Courier, monospace;
            font-size: 0.9em;
        }
        
        .text-center {
            text-align: center;
        }
        
        .text-right {
            text-align: right;
        }
        
        .mb-1 {
            margin-bottom: 1rem;
        }
        
        .mb-2 {
            margin-bottom: 2rem;
        }
    """


def get_javascript() -> str:
    """Minimal JS for Audit report"""
    return """
        // No interactive elements in Audit reports
        // All evidence is in Appendix, not togglable
    """
