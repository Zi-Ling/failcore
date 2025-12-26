# failcore/cli/renderers/html/styles.py
"""
CSS for Forensic Audit Report - Legal Document Style
"""

def get_css() -> str:
    """Get CSS styles for forensic audit report (A4 Document)"""
    return """
        /* Print-First Design */
        @media print {
            body {
                background: white;
                padding: 0;
            }
            .container {
                box-shadow: none;
                border: none;
                max-width: 100%;
                page-break-after: always;
            }
            .page-header, .page-footer {
                position: fixed;
            }
            .page-header { top: 0; }
            .page-footer { bottom: 0; }
            .section {
                page-break-inside: avoid;
            }
            .no-print {
                display: none !important;
            }
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Georgia, "Times New Roman", serif;
            line-height: 1.6;
            color: #1a1a1a;
            background: #e5e7eb;
            padding: 2rem;
        }
        
        /* A4 Paper Container */
        .container {
            max-width: 210mm;
            min-height: 297mm;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            position: relative;
            padding: 3cm 2.5cm 3cm 2.5cm; /* A4 margins */
        }
        
        /* OFFICIAL RECORD Watermark */
        .container::before {
            content: "OFFICIAL RECORD";
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-45deg);
            font-size: 5rem;
            font-weight: 700;
            color: rgba(0, 0, 0, 0.02);
            letter-spacing: 0.5rem;
            pointer-events: none;
            z-index: 0;
            font-family: serif;
        }
        
        /* Page Header */
        .page-header {
            position: absolute;
            top: 1cm;
            left: 2.5cm;
            right: 2.5cm;
            padding-bottom: 0.5cm;
            border-bottom: 2px solid #000;
            font-size: 0.7rem;
            display: flex;
            justify-content: space-between;
            font-family: "Courier New", monospace;
        }
        
        /* Page Footer */
        .page-footer {
            position: absolute;
            bottom: 1cm;
            left: 2.5cm;
            right: 2.5cm;
            padding-top: 0.5cm;
            border-top: 1px solid #ccc;
            font-size: 0.65rem;
            color: #666;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        /* Document Header */
        .doc-header {
            margin-bottom: 3rem;
            border-bottom: 4px double #000;
            padding-bottom: 1.5rem;
            position: relative;
            z-index: 1;
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
        
        /* Section Numbering */
        .section {
            margin-bottom: 2.5rem;
            position: relative;
            z-index: 1;
        }
        
        .section-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #000;
            font-family: Georgia, serif;
        }
        
        .section-content {
            font-size: 0.95rem;
            line-height: 1.7;
            text-align: justify;
        }
        
        /* Executive Summary Box */
        .exec-summary-box {
            padding: 1rem 1.5rem;
            background: #f9f9f9;
            border-left: 4px solid #000;
            margin-bottom: 1.5rem;
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
        
        /* Incident Card (NOT Web Card!) */
        .incident-record {
            margin-bottom: 2rem;
            border: 2px solid #000;
            break-inside: avoid;
        }
        
        .incident-header {
            background: #f5f5f5;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #000;
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }
        
        .incident-id {
            font-weight: 700;
            font-family: "Courier New", monospace;
            font-size: 0.9rem;
        }
        
        .severity-label {
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.2rem 0.6rem;
            border: 1px solid #000;
            background: white;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .incident-body {
            padding: 1rem;
            font-size: 0.9rem;
        }
        
        .incident-field {
            margin-bottom: 0.75rem;
        }
        
        .field-label {
            font-weight: 700;
            display: block;
            margin-bottom: 0.25rem;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .field-value {
            padding-left: 1rem;
            color: #333;
        }
        
        /* Appendix Reference */
        .appendix-ref {
            font-style: italic;
            color: #666;
            font-size: 0.85rem;
            border-left: 2px solid #ccc;
            padding-left: 1rem;
            margin: 1rem 0;
        }
        
        /* Appendix Section */
        .appendix-section {
            page-break-before: always;
            margin-top: 3rem;
            border-top: 3px double #000;
            padding-top: 2rem;
        }
        
        .appendix-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 1rem;
            text-transform: uppercase;
        }
        
        .evidence-block {
            background: #f9f9f9;
            border: 1px solid #ccc;
            padding: 1rem;
            font-family: "Courier New", monospace;
            font-size: 0.75rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
        
        /* Signature Section */
        .signature-section {
            margin-top: 4rem;
            padding-top: 2rem;
            border-top: 3px double #000;
            page-break-inside: avoid;
        }
        
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
        
        /* Monospace for technical fields */
        .mono {
            font-family: "Courier New", Courier, monospace;
            font-size: 0.9em;
        }
        
        /* QR Code Placeholder */
        .qr-placeholder {
            width: 80px;
            height: 80px;
            border: 2px solid #000;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.6rem;
            font-weight: 700;
        }
        
        /* Utility */
        .text-center { text-align: center; }
        .text-right { text-align: right; }
        .mb-1 { margin-bottom: 1rem; }
        .mb-2 { margin-bottom: 2rem; }
    """


def get_javascript() -> str:
    """Minimal JS for audit report"""
    return """
        // No interactive elements in audit reports
        // All evidence is in Appendix, not togglable
    """
