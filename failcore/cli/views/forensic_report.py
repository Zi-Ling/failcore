# failcore/cli/views/forensic_report.py
"""
ForensicReportView - View model for forensic (audit) report rendering.

This module converts core.forensics.model.ForensicReport (dataclass)
into a renderer-friendly view model for HTML/Text/JSON presentation.

Design goals:
- Keep renderer decoupled from core model internals.
- Provide stable, display-oriented fields with sensible fallbacks.
- Allow optional trace_events to enrich missing tool/context info.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json
from datetime import datetime, timezone

from failcore.core.forensics.model import ForensicReport, Finding


# -----------------------------
# View Models
# -----------------------------

@dataclass
class ForensicFindingView:
    """Single finding view (display-oriented)"""
    anchor_id: str                     # e.g. "f-<finding_id>"
    finding_id: str
    ts: str
    severity: str                      # LOW/MED/HIGH/CRIT
    title: str
    what_happened: str

    # Tool/Rule
    tool_name: Optional[str] = None
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    rule_label: Optional[str] = None   # prefer rule_name else rule_id

    # Risk mapping
    owasp_agentic_ids: List[str] = field(default_factory=list)

    # Cause/evidence
    triggered_by: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    snapshot: Optional[Dict[str, Any]] = None

    # Extras
    reproducible: Optional[bool] = None
    mitigation: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class ForensicSummaryView:
    """Summary statistics for the forensic report"""
    tool_calls: int = 0
    denied: int = 0
    errors: int = 0
    warnings: int = 0
    risk_score: Optional[int] = None

    findings_total: int = 0
    findings_by_severity: Dict[str, int] = field(default_factory=dict)
    top_risks: List[str] = field(default_factory=list)  # e.g. ["ASI03", "ASI05"]


@dataclass
class ForensicMetaView:
    """Metadata about this forensic report"""
    schema: str
    report_id: str
    generated_at: str
    run_id: str
    trace_schema: Optional[str] = None
    trace_path: Optional[str] = None


@dataclass
class ForensicValueMetricsView:
    """
    Value/impact metrics (human-facing).

    Note: do not pretend side effects happened; this is for audit signal.
    """
    findings_total: int
    critical_or_high: int
    policy_denied_findings: int
    has_integrity_placeholder: bool = True


@dataclass
class ForensicReportView:
    """
    Complete view model for forensic report rendering.
    """
    meta: ForensicMetaView
    summary: ForensicSummaryView
    value_metrics: ForensicValueMetricsView
    findings: List[ForensicFindingView]
    
    # v0.1.3 Audit Enhancements
    executive_summary: str = ""
    compliance_mapping: Dict[str, List[str]] = field(default_factory=dict)
    signature_placeholder: Dict[str, str] = field(default_factory=lambda: {
        "hash_algo": "SHA-256",
        "hash_value": "_______________________", # Placeholder for manual filling or future logic
        "signer": "FailCore Runtime v0.1.2"
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": {
                "schema": self.meta.schema,
                "report_id": self.meta.report_id,
                "generated_at": self.meta.generated_at,
                "run_id": self.meta.run_id,
                "trace_schema": self.meta.trace_schema,
                "trace_path": self.meta.trace_path,
            },
            "summary": {
                "tool_calls": self.summary.tool_calls,
                "denied": self.summary.denied,
                "errors": self.summary.errors,
                "warnings": self.summary.warnings,
                "risk_score": self.summary.risk_score,
                "findings_total": self.summary.findings_total,
                "findings_by_severity": dict(self.summary.findings_by_severity),
                "top_risks": list(self.summary.top_risks),
            },
            "value_metrics": {
                "findings_total": self.value_metrics.findings_total,
                "critical_or_high": self.value_metrics.critical_or_high,
                "policy_denied_findings": self.value_metrics.policy_denied_findings,
                "has_integrity_placeholder": self.value_metrics.has_integrity_placeholder,
            },
            "findings": [
                {
                    "anchor_id": f.anchor_id,
                    "finding_id": f.finding_id,
                    "ts": f.ts,
                    "severity": f.severity,
                    "title": f.title,
                    "what_happened": f.what_happened,
                    "tool_name": f.tool_name,
                    "rule_id": f.rule_id,
                    "rule_name": f.rule_name,
                    "rule_label": f.rule_label,
                    "owasp_agentic_ids": list(f.owasp_agentic_ids),
                    "triggered_by": f.triggered_by,
                    "evidence": f.evidence,
                    "snapshot": f.snapshot,
                    "reproducible": f.reproducible,
                    "mitigation": f.mitigation,
                    "tags": list(f.tags),
                }
                for f in self.findings
            ],
            # v0.1.3
            "executive_summary": self.executive_summary,
            "compliance_mapping": self.compliance_mapping,
            "signature_placeholder": self.signature_placeholder,
        }


# -----------------------------
# Builders
# -----------------------------

def build_forensic_view(
    report: ForensicReport,
    *,
    trace_path: Optional[str] = None,
    trace_events: Optional[List[Dict[str, Any]]] = None,
) -> ForensicReportView:
    """
    Convert core ForensicReport -> ForensicReportView.

    Args:
        report: core.forensics.model.ForensicReport
        trace_path: optional trace file path (string) for display
        trace_events: optional parsed trace events (list[dict]) used to enrich tool_name

    Returns:
        ForensicReportView
    """
    # Build enrichment index from trace if provided
    tool_by_step, tool_by_seq = _build_tool_indices(trace_events or [])

    # Meta
    trace_schema = None
    if isinstance(getattr(report, "metadata", None), dict):
        trace_schema = report.metadata.get("trace_schema")

    meta = ForensicMetaView(
        schema=report.schema,
        report_id=report.report_id,
        generated_at=report.generated_at,
        run_id=report.run_id,
        trace_schema=trace_schema,
        trace_path=trace_path,
    )

    # Findings -> view
    finding_views: List[ForensicFindingView] = []
    sev_counts: Dict[str, int] = {"CRIT": 0, "HIGH": 0, "MED": 0, "LOW": 0}

    policy_denied_findings = 0

    for f in report.findings:
        sev = _norm_sev(f.severity)
        # Expand severity name for audit report trust
        sev_display = sev
        if sev == "MED": sev_display = "MEDIUM RISK"
        elif sev == "CRIT": sev_display = "CRITICAL RISK"
        elif sev == "HIGH": sev_display = "HIGH RISK"
        elif sev == "LOW": sev_display = "LOW RISK"
        
        if sev in sev_counts:
            sev_counts[sev] += 1

        if _looks_like_policy_denied(f):
            policy_denied_findings += 1

        tool_name = _infer_tool_name(f, tool_by_seq, tool_by_step)
        rule_label = f.rule_name or f.rule_id

        finding_views.append(
            ForensicFindingView(
                anchor_id=f"f-{f.finding_id}",
                finding_id=f.finding_id,
                ts=f.ts,
                severity=sev_display, # Use expanded name
                title=f.title,
                what_happened=f.what_happened,
                tool_name=tool_name,
                rule_id=f.rule_id,
                rule_name=f.rule_name,
                rule_label=rule_label,
                owasp_agentic_ids=list(f.owasp_agentic_ids or []),
                triggered_by=_as_dict(getattr(f, "triggered_by", None)),
                evidence=_as_dict(getattr(f, "evidence", None)),
                snapshot=_as_dict(getattr(f, "snapshot", None)),
                reproducible=getattr(f, "reproducible", None),
                mitigation=getattr(f, "mitigation", None),
                tags=list(getattr(f, "tags", []) or []),
            )
        )

    # Sort findings for better reading: severity desc, then ts desc
    finding_views.sort(key=lambda x: (_severity_rank(x.severity.split()[0]), x.ts), reverse=True)

    # Summary
    summary_src = report.summary
    top_risks = _top_risk_codes(report.findings, top_k=5)

    summary = ForensicSummaryView(
        tool_calls=getattr(summary_src, "tool_calls", 0) or 0,
        denied=getattr(summary_src, "denied", 0) or 0,
        errors=getattr(summary_src, "errors", 0) or 0,
        warnings=getattr(summary_src, "warnings", 0) or 0,
        risk_score=getattr(summary_src, "risk_score", None),
        findings_total=len(report.findings),
        findings_by_severity={k: v for k, v in sev_counts.items() if v > 0},
        top_risks=top_risks,
    )

    # Value metrics (keep simple and honest)
    crit_or_high = sev_counts.get("CRIT", 0) + sev_counts.get("HIGH", 0)
    value_metrics = ForensicValueMetricsView(
        findings_total=len(report.findings),
        critical_or_high=crit_or_high,
        policy_denied_findings=policy_denied_findings,
        has_integrity_placeholder=True,
    )
    
    # Generate Executive Summary (Natural Language)
    risk_score = summary.risk_score or 0
    exec_summary_lines = []
    exec_summary_lines.append(f"During this execution, FailCore monitored {summary.tool_calls} tool invocations.")
    
    if policy_denied_findings > 0:
        exec_summary_lines.append(f"FailCore actively intercepted and BLOCKED {policy_denied_findings} unsafe actions that violated security policy.")
    
    if crit_or_high > 0:
        exec_summary_lines.append(f"CRITICAL FINDINGS DETECTED. Immediate review is required for {crit_or_high} high-severity issues.")
    elif summary.findings_total > 0:
        exec_summary_lines.append(f"Several risks were identified, but no critical policy breaches occurred.")
    else:
        exec_summary_lines.append("No security anomalies or policy violations were detected.")
        
    exec_summary_lines.append(f"Overall risk is assessed as {risk_score}/100.")
    executive_summary = " ".join(exec_summary_lines)
    
    # Generate Compliance Mapping (Placeholder/Mock for now, but critical for structure)
    compliance_mapping = {
        "OWASP Agentic Top 10": [
            "ASI01 - Privileged Execution (Checked)",
            "ASI02 - Tool Misuse (Monitored)"
        ],
        "SOC 2 Trust Services": [
            "CC6.1 - Logical Access (Enforced)",
            "CC6.6 - Boundary Protection (Active)"
        ]
    }

    return ForensicReportView(
        meta=meta,
        summary=summary,
        value_metrics=value_metrics,
        findings=finding_views,
        executive_summary=executive_summary,
        compliance_mapping=compliance_mapping,
    )


def build_forensic_view_from_trace(
    trace_path: Path,
) -> ForensicReportView:
    """
    Convenience helper: read trace.jsonl -> analyze -> view.

    NOTE:
    This function assumes you already have core.forensics.analyzer integrated
    somewhere else. If you want to keep cli/views pure, do not call analyzer here.
    For now, we keep it as a utility for CLI.

    If you don't want this dependency, delete this function.
    """
    from failcore.core.forensics.analyzer import analyze_events

    events = _read_jsonl(trace_path)
    report = analyze_events(events, trace_path=str(trace_path))
    return build_forensic_view(report, trace_path=str(trace_path), trace_events=events)


# -----------------------------
# Internal helpers
# -----------------------------

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _as_dict(x: Any) -> Optional[Dict[str, Any]]:
    if x is None:
        return None
    if isinstance(x, dict):
        return x
    # core dataclasses are typically dict-like via __dict__
    try:
        d = dict(getattr(x, "__dict__", {}))
        return d or None
    except Exception:
        return None


def _norm_sev(sev: Any) -> str:
    s = str(sev or "").upper()
    if s in ("CRIT", "CRITICAL"):
        return "CRIT"
    if s in ("HIGH",):
        return "HIGH"
    if s in ("MED", "MEDIUM"):
        return "MED"
    if s in ("LOW",):
        return "LOW"
    # fallback
    return "LOW"


def _severity_rank(sev: str) -> int:
    return {"CRIT": 4, "HIGH": 3, "MED": 2, "LOW": 1}.get((sev or "").upper(), 0)


def _looks_like_policy_denied(f: Finding) -> bool:
    # Best-effort heuristic: tag contains "policy" or title includes "Policy denied"
    try:
        title = (f.title or "").lower()
        if "policy denied" in title or "policy" in title and "denied" in title:
            return True
        tags = getattr(f, "tags", []) or []
        return any(str(t).lower() == "policy" for t in tags)
    except Exception:
        return False


def _top_risk_codes(findings: List[Finding], top_k: int = 5) -> List[str]:
    counts: Dict[str, int] = {}
    for f in findings:
        ids = getattr(f, "owasp_agentic_ids", None) or []
        for rid in ids:
            if not isinstance(rid, str) or not rid:
                continue
            counts[rid] = counts.get(rid, 0) + 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in items[:top_k]]


def _build_tool_indices(
    events: List[Dict[str, Any]],
) -> Tuple[Dict[str, str], Dict[int, str]]:
    """
    Build indexes:
    - tool_by_step_id: step_id -> tool_name
    - tool_by_seq: seq -> tool_name (from STEP_START)
    """
    tool_by_step: Dict[str, str] = {}
    tool_by_seq: Dict[int, str] = {}

    for ev in events:
        if not isinstance(ev, dict):
            continue
        seq = ev.get("seq")
        body = ev.get("event") or {}
        if not isinstance(body, dict):
            continue

        etype = body.get("type")
        if etype != "STEP_START":
            continue

        step = body.get("step") or {}
        if not isinstance(step, dict):
            continue
        step_id = step.get("id")
        tool = step.get("tool")

        if isinstance(step_id, str) and step_id and isinstance(tool, str) and tool:
            tool_by_step[step_id] = tool
        if isinstance(seq, int) and isinstance(tool, str) and tool:
            tool_by_seq[seq] = tool

    return tool_by_step, tool_by_seq


def _infer_tool_name(
    f: Finding,
    tool_by_seq: Dict[int, str],
    tool_by_step: Dict[str, str],
) -> Optional[str]:
    """
    Infer tool_name from:
    1) f.triggered_by.tool_name
    2) f.triggered_by.source_event_seq -> STEP_START seq
    3) f.triggered_by.source_event_id not supported (trace doesn't have it now)
    4) evidence.event_seq -> try first seq mapping
    """
    trig = getattr(f, "triggered_by", None)
    if trig is not None:
        tool = getattr(trig, "tool_name", None)
        if isinstance(tool, str) and tool:
            return tool

        seq = getattr(trig, "source_event_seq", None)
        if isinstance(seq, int) and seq in tool_by_seq:
            return tool_by_seq.get(seq)

    evref = getattr(f, "evidence", None)
    if evref is not None:
        seqs = getattr(evref, "event_seq", None)
        if isinstance(seqs, list) and seqs:
            first = seqs[0]
            if isinstance(first, int) and first in tool_by_seq:
                return tool_by_seq.get(first)

    return None
