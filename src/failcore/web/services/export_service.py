# failcore/web/services/export_service.py
"""
Export Service - generate static HTML/Markdown exports for incident replay

Exports incident replay data as standalone HTML files that can be shared.
"""

from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from .replay_service import get_replay_service
from .replay_schema import IncidentTape
from failcore.utils.paths import get_failcore_root


class ExportService:
    """
    Service for exporting incident replay data as static files.
    """
    
    def __init__(self):
        """Initialize export service"""
        self.replay_service = get_replay_service()
    
    def export_replay_html(self, run_id: str, output_path: Optional[Path] = None) -> Path:
        """
        Export incident replay as standalone HTML file.
        
        Args:
            run_id: Run ID
            output_path: Optional output path (defaults to artifacts directory)
        
        Returns:
            Path to exported HTML file
        """
        # Get incident tape
        incident_tape = self.replay_service.get_incident_tape(run_id)
        
        # Determine output path
        if output_path is None:
            artifacts_dir = get_failcore_root() / "artifacts"
            artifacts_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = artifacts_dir / f"replay_{run_id}_{timestamp}.html"
        
        # Generate HTML content
        html_content = self._render_export_html(incident_tape, run_id)
        
        # Write to file
        output_path.write_text(html_content, encoding='utf-8')
        
        return output_path
    
    def _render_export_html(self, incident_tape: IncidentTape, run_id: str) -> str:
        """
        Render incident tape as standalone HTML.
        
        Args:
            incident_tape: Incident tape data
            run_id: Run ID
        
        Returns:
            HTML content as string
        """
        tape_dict = incident_tape.to_dict()
        frames = tape_dict.get("frames", [])
        events = tape_dict.get("events", [])
        meta = tape_dict.get("meta", {})
        budget = tape_dict.get("budget")
        cost_curve = tape_dict.get("cost_curve", [])
        
        # Filter key frames (blocked, high-risk, or with anomalies)
        key_frames = [
            f for f in frames
            if f.get("status") == "BLOCKED" or
               f.get("error_code") or
               (f.get("anomalies") and len(f.get("anomalies", [])) > 0) or
               (f.get("tool_metadata", {}).get("risk_level") == "high")
        ]
        
        # Generate HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Incident Replay: {run_id} - FailCore</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #1a1d21;
            background: #f5f6f8;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #1a1d21;
        }}
        
        h2 {{
            font-size: 1.5rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: #1a1d21;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 0.5rem;
        }}
        
        .meta {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
            padding: 1rem;
            background: #f5f6f8;
            border-radius: 4px;
        }}
        
        .meta-item {{
            display: flex;
            flex-direction: column;
        }}
        
        .meta-label {{
            font-size: 0.75rem;
            color: #5f6368;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }}
        
        .meta-value {{
            font-size: 0.875rem;
            color: #1a1d21;
            font-weight: 500;
        }}
        
        .summary {{
            margin-bottom: 2rem;
            padding: 1rem;
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 4px;
        }}
        
        .summary h3 {{
            font-size: 1rem;
            margin-bottom: 0.5rem;
            color: #856404;
        }}
        
        .summary p {{
            font-size: 0.875rem;
            color: #856404;
        }}
        
        .key-frames {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .frame-card {{
            padding: 1rem;
            background: #f5f6f8;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            border-left: 4px solid #3b82f6;
        }}
        
        .frame-card.blocked {{
            border-left-color: #ef4444;
            background: #fee2e2;
        }}
        
        .frame-card.high-risk {{
            border-left-color: #f59e0b;
            background: #fef3c7;
        }}
        
        .frame-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}
        
        .frame-seq {{
            font-family: monospace;
            font-weight: 600;
            color: #1a1d21;
        }}
        
        .frame-status {{
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            border-radius: 4px;
            border: 1px solid;
        }}
        
        .frame-status.blocked {{
            color: #ef4444;
            border-color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
        }}
        
        .frame-status.ok {{
            color: #10b981;
            border-color: #10b981;
            background: rgba(16, 185, 129, 0.1);
        }}
        
        .frame-tool {{
            font-size: 0.875rem;
            font-weight: 500;
            color: #1a1d21;
            margin-bottom: 0.5rem;
        }}
        
        .frame-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .badge {{
            padding: 0.25rem 0.5rem;
            font-size: 0.75rem;
            border-radius: 4px;
            font-weight: 500;
        }}
        
        .badge.risk-high {{
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid #ef4444;
        }}
        
        .badge.side-effect-exec {{
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid #ef4444;
        }}
        
        .badge.side-effect-network {{
            background: rgba(245, 158, 11, 0.1);
            color: #f59e0b;
            border: 1px solid #f59e0b;
        }}
        
        .badge.side-effect-fs {{
            background: rgba(59, 130, 246, 0.1);
            color: #3b82f6;
            border: 1px solid #3b82f6;
        }}
        
        .frame-decision {{
            font-size: 0.875rem;
            color: #5f6368;
            font-style: italic;
            margin-top: 0.5rem;
            padding: 0.5rem;
            background: white;
            border-radius: 4px;
        }}
        
        .frame-error {{
            font-size: 0.875rem;
            color: #ef4444;
            margin-top: 0.5rem;
            padding: 0.5rem;
            background: #fee2e2;
            border-radius: 4px;
        }}
        
        .cost-section {{
            margin-top: 2rem;
            padding: 1rem;
            background: #f5f6f8;
            border-radius: 4px;
        }}
        
        .cost-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}
        
        .cost-item {{
            display: flex;
            flex-direction: column;
        }}
        
        .cost-label {{
            font-size: 0.75rem;
            color: #5f6368;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }}
        
        .cost-value {{
            font-size: 1.25rem;
            font-weight: 600;
            color: #1a1d21;
        }}
        
        .footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #e0e0e0;
            font-size: 0.75rem;
            color: #5f6368;
            text-align: center;
        }}
        
        pre {{
            background: #f5f6f8;
            padding: 0.75rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.75rem;
            margin-top: 0.5rem;
        }}
        
        code {{
            font-family: 'Courier New', monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Incident Replay Report</h1>
        
        <div class="meta">
            <div class="meta-item">
                <div class="meta-label">Run ID</div>
                <div class="meta-value">{run_id}</div>
            </div>
            {f'<div class="meta-item"><div class="meta-label">Command</div><div class="meta-value">{meta.get("command", "N/A")}</div></div>' if meta.get("command") else ''}
            {f'<div class="meta-item"><div class="meta-label">Created At</div><div class="meta-value">{meta.get("created_at", "N/A")}</div></div>' if meta.get("created_at") else ''}
            {f'<div class="meta-item"><div class="meta-label">Status</div><div class="meta-value">{meta.get("status", "N/A")}</div></div>' if meta.get("status") else ''}
        </div>
        
        <div class="summary">
            <h3>Incident Summary</h3>
            <p>
                This run encountered {len(events)} incident event(s) across {len(frames)} execution steps.
                {len(key_frames)} key frame(s) were identified with blocked operations, high-risk tools, or anomalies.
            </p>
        </div>
        
        <h2>Key Frames</h2>
        <div class="key-frames">
"""
        
        # Render key frames
        for frame in key_frames[:20]:  # Limit to 20 frames
            status = (frame.get("status") or "PENDING").lower()
            tool = frame.get("tool", "Unknown")
            seq = frame.get("seq", 0)
            tool_metadata = frame.get("tool_metadata", {})
            risk_level = tool_metadata.get("risk_level", "medium")
            side_effect = tool_metadata.get("side_effect", "").upper()
            decision = frame.get("decision")
            error_code = frame.get("error_code")
            
            card_class = "frame-card"
            if status == "blocked":
                card_class += " blocked"
            elif risk_level == "high":
                card_class += " high-risk"
            
            badges_html = ""
            if side_effect:
                badges_html += f'<span class="badge side-effect-{side_effect.lower()}">{side_effect}</span>'
            if risk_level == "high":
                badges_html += '<span class="badge risk-high">HIGH RISK</span>'
            
            html += f"""
            <div class="{card_class}">
                <div class="frame-header">
                    <span class="frame-seq">Step #{seq}</span>
                    <span class="frame-status {status}">{status.upper()}</span>
                </div>
                <div class="frame-tool">{tool}</div>
                {f'<div class="frame-badges">{badges_html}</div>' if badges_html else ''}
                {f'<div class="frame-decision">{decision}</div>' if decision else ''}
                {f'<div class="frame-error">Error: {error_code}</div>' if error_code else ''}
            </div>
"""
        
        html += """
        </div>
"""
        
        # Cost section
        if cost_curve:
            last_point = cost_curve[-1]
            html += f"""
        <h2>Cost Summary</h2>
        <div class="cost-section">
            <div class="cost-summary">
                <div class="cost-item">
                    <div class="cost-label">Total Cost</div>
                    <div class="cost-value">${last_point.get("cum_cost_usd", 0):.6f}</div>
                </div>
                <div class="cost-item">
                    <div class="cost-label">Total Tokens</div>
                    <div class="cost-value">{last_point.get("cum_tokens", 0):,}</div>
                </div>
                <div class="cost-item">
                    <div class="cost-label">Steps</div>
                    <div class="cost-value">{len(cost_curve)}</div>
                </div>
            </div>
"""
            if budget:
                html += f"""
            <div style="margin-top: 1rem; padding: 0.75rem; background: white; border-radius: 4px;">
                <div style="font-size: 0.75rem; color: #5f6368; margin-bottom: 0.5rem;">Budget Limits</div>
"""
                if budget.get("max_cost_usd"):
                    html += f'<div style="font-size: 0.875rem; margin-bottom: 0.25rem;">Max Cost: ${budget.get("max_cost_usd"):.2f}</div>'
                if budget.get("max_tokens"):
                    html += f'<div style="font-size: 0.875rem; margin-bottom: 0.25rem;">Max Tokens: {budget.get("max_tokens"):,}</div>'
                html += """
            </div>
"""
            html += """
        </div>
"""
        
        # Footer
        html += f"""
        <div class="footer">
            <div>Generated by FailCore on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
            <div style="margin-top: 0.5rem;">Run ID: {run_id}</div>
            <div style="margin-top: 0.25rem; font-size: 0.6875rem;">This is a static export. For interactive replay, visit the FailCore web UI.</div>
        </div>
    </div>
</body>
</html>
"""
        
        return html


# Singleton instance
_export_service: Optional[ExportService] = None


def get_export_service() -> ExportService:
    """Get export service singleton"""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service


__all__ = ["ExportService", "get_export_service"]
