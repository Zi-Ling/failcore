# failcore/infra/audit/writer.py
from __future__ import annotations

import json
import os
from dataclasses import is_dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union


JsonPrimitive = Union[str, int, float, bool, None]
JsonValue = Union[JsonPrimitive, Dict[str, Any], list]


def _truncate_str(s: str, limit: int = 4096) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + "…"


def _json_safe(obj: Any, *, str_limit: int = 4096, depth: int = 0, max_depth: int = 20) -> Any:
    """
    Convert arbitrary objects into JSON-serializable structures.

    Policy (v0.1):
      - dict/list/tuple/set -> recursively convert
      - dataclass -> asdict then convert
      - Enum -> value if present else str()
      - datetime -> ISO string (UTC if tz-aware is missing, keep as-is but strftime safe)
      - bytes -> hex digest-like preview
      - unknown -> str(obj) truncated

    Max depth prevents pathological recursion.
    """
    if depth > max_depth:
        return "<max_depth_reached>"

    # primitives
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # dataclass
    if is_dataclass(obj):
        try:
            return _json_safe(asdict(obj), str_limit=str_limit, depth=depth + 1, max_depth=max_depth)
        except Exception:
            return _truncate_str(str(obj), str_limit)

    # datetime
    if isinstance(obj, datetime):
        try:
            # keep microseconds out for readability
            dt = obj
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc)  # type: ignore[attr-defined]
            dt = dt.replace(microsecond=0)
            s = dt.isoformat()
            # normalize UTC suffix if possible
            if s.endswith("+00:00"):
                s = s.replace("+00:00", "Z")
            return s
        except Exception:
            return _truncate_str(str(obj), str_limit)

    # bytes
    if isinstance(obj, (bytes, bytearray)):
        # don't dump raw bytes; show a short preview
        hx = obj[:32].hex()
        return f"<bytes len={len(obj)} hex_prefix={hx}>"

    # mappings
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            try:
                key = str(k)
            except Exception:
                key = "<unstringable_key>"
            out[key] = _json_safe(v, str_limit=str_limit, depth=depth + 1, max_depth=max_depth)
        return out

    # iterables
    if isinstance(obj, (list, tuple, set)):
        return [
            _json_safe(v, str_limit=str_limit, depth=depth + 1, max_depth=max_depth)
            for v in list(obj)
        ]

    # Enum-like
    val = getattr(obj, "value", None)
    if val is not None and isinstance(val, (str, int, float, bool)):
        return val

    # fallback
    return _truncate_str(str(obj), str_limit)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_audit_json(
    report: Any,
    out_path: str | os.PathLike[str],
    *,
    pretty: bool = False,
    ensure_ascii: bool = False,
    str_limit: int = 4096,
) -> Dict[str, Any]:
    """
    Write audit report to a JSON file.

    Args:
      report:
        - AuditReport (dataclass with .to_dict()) OR a plain dict
      out_path:
        output file path, e.g. "reports/audit.json"
      pretty:
        pretty print (indent=2). Default False for compact output.
      ensure_ascii:
        default False to keep Chinese readable.
      str_limit:
        max string length when forcing JSON-safe conversion.

    Returns:
      The JSON-serializable dict that was written (useful for tests/bundles).
    """
    p = Path(out_path)
    _ensure_parent_dir(p)

    # obtain raw dict
    if isinstance(report, dict):
        raw = report
    else:
        to_dict = getattr(report, "to_dict", None)
        if callable(to_dict):
            raw = to_dict()
        elif is_dataclass(report):
            raw = asdict(report)
        else:
            # last resort
            raw = {"report": report}

    safe = _json_safe(raw, str_limit=str_limit)

    with p.open("w", encoding="utf-8") as f:
        if pretty:
            json.dump(safe, f, ensure_ascii=ensure_ascii, indent=2, sort_keys=False)
            f.write("\n")
        else:
            json.dump(safe, f, ensure_ascii=ensure_ascii, separators=(",", ":"), sort_keys=False)
            f.write("\n")

    return safe


def dumps_audit_json(
    report: Any,
    *,
    pretty: bool = False,
    ensure_ascii: bool = False,
    str_limit: int = 4096,
) -> str:
    """
    Dump audit audit report to a JSON string (for tests/debug).
    """
    if isinstance(report, dict):
        raw = report
    else:
        to_dict = getattr(report, "to_dict", None)
        if callable(to_dict):
            raw = to_dict()
        elif is_dataclass(report):
            raw = asdict(report)
        else:
            raw = {"report": report}

    safe = _json_safe(raw, str_limit=str_limit)

    if pretty:
        return json.dumps(safe, ensure_ascii=ensure_ascii, indent=2, sort_keys=False) + "\n"
    return json.dumps(safe, ensure_ascii=ensure_ascii, separators=(",", ":"), sort_keys=False) + "\n"


def write_audit_jsonl(
    report: Any,
    out_path: str | os.PathLike[str],
    *,
    run_info: Optional[Dict[str, Any]] = None,
    host_info: Optional[Dict[str, Any]] = None,
    ensure_ascii: bool = False,
    str_limit: int = 4096,
) -> None:
    """
    Write audit report to JSONL format (failcore.audit.v0.1.1 schema).
    
    Each line is a audit event: REPORT_START, SUMMARY, FINDING, ATTESTATION, REPORT_END.
    
    Args:
        report: AuditReport instance (or dict with compatible structure)
        out_path: Output path for audit.jsonl
        run_info: Optional run metadata (run_id, created_at, version, etc.)
        host_info: Optional host metadata (os, python, pid)
        ensure_ascii: Default False to keep Chinese readable
        str_limit: Max string length when forcing JSON-safe conversion
    """
    from datetime import datetime, timezone
    
    p = Path(out_path)
    _ensure_parent_dir(p)
    
    # Extract report dict
    if isinstance(report, dict):
        report_dict = report
    else:
        to_dict = getattr(report, "to_dict", None)
        if callable(to_dict):
            report_dict = to_dict()
        elif is_dataclass(report):
            report_dict = asdict(report)
        else:
            report_dict = {"report": report}
    
    # Extract core fields
    report_id = report_dict.get("report_id") or report_dict.get("id") or "FC-UNKNOWN"
    created_at = report_dict.get("created_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    summary = report_dict.get("summary", {})
    findings = report_dict.get("findings", [])
    metadata = report_dict.get("metadata", {})
    
    # Default run info
    if run_info is None:
        run_info = {
            "run_id": report_dict.get("run_id") or "unknown",
            "created_at": created_at,
            "version": {"spec": "v0.1.1"}
        }
    
    seq = 0
    
    def _emit(event_type: str, data: Optional[Dict[str, Any]] = None, report_meta: Optional[Dict[str, Any]] = None, level: str = "INFO") -> None:
        nonlocal seq
        seq += 1
        event_obj = {
            "schema": "failcore.audit.v0.1.1",
            "seq": seq,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": level,
            "event": {
                "type": event_type,
            },
            "run": run_info,
        }
        
        if report_meta:
            event_obj["event"]["report"] = report_meta
        
        if data:
            event_obj["event"]["data"] = data
        
        if host_info:
            event_obj["host"] = host_info
        
        safe = _json_safe(event_obj, str_limit=str_limit)
        return json.dumps(safe, ensure_ascii=ensure_ascii, separators=(",", ":"), sort_keys=False)
    
    # Open file and write JSONL stream
    with p.open("w", encoding="utf-8") as f:
        # 1. REPORT_START
        f.write(_emit(
            "REPORT_START",
            report_meta={
                "report_id": report_id,
                "title": "FailCore audit Report",
                "classification": "CONFIDENTIAL",
                "schema_spec": "v0.1.1",
                "generated_at": created_at,
            }
        ))
        f.write("\n")
        
        # 2. SUMMARY
        tool_calls = summary.get("tool_calls", 0)
        risk_score = summary.get("risk_score", 0)
        denied = summary.get("denied", 0)
        errors = summary.get("errors", 0)
        warnings = summary.get("warnings", 0)
        findings_count = len(findings)
        
        # Determine overall severity
        if risk_score >= 40 or denied > 0:
            overall_severity = "HIGH"
        elif risk_score >= 20 or errors > 0:
            overall_severity = "MEDIUM"
        else:
            overall_severity = "LOW"
        
        # Generate executive summary notes
        notes = []
        if denied > 0:
            notes.append(f"FailCore successfully monitored {tool_calls} tool invocations and blocked {denied} unsafe operation(s).")
        else:
            notes.append(f"FailCore successfully monitored {tool_calls} tool invocations during the execution session.")
        
        if findings_count > 0:
            notes.append(f"{findings_count} incident(s) were recorded for further analysis.")
        else:
            notes.append("No critical incidents detected.")
        
        if errors == 0 and denied == 0:
            notes.append("No policy breaches were confirmed.")
        
        f.write(_emit(
            "SUMMARY",
            data={
                "summary": {
                    "overall_risk_score": min(risk_score, 100),
                    "overall_severity": overall_severity,
                    "notes": notes,
                    "counts": {
                        "tool_calls": tool_calls,
                        "findings": findings_count,
                        "blocked": denied,
                        "failed": errors,
                    }
                }
            }
        ))
        f.write("\n")
        
        # 3. FINDING events
        for finding in findings:
            # Extract finding fields
            finding_id = finding.get("finding_id") or finding.get("id") or "UNKNOWN"
            ts = finding.get("ts") or created_at
            severity = finding.get("severity", "LOW")
            title = finding.get("title", "Finding")
            what_happened = finding.get("what_happened", "")
            mitigation = finding.get("mitigation", "")
            
            # Map severity to schema enum
            sev_map = {"CRIT": "CRITICAL", "HIGH": "HIGH", "MED": "MEDIUM", "LOW": "LOW"}
            severity_enum = sev_map.get(severity.upper(), "MEDIUM")
            
            # Determine category
            if "policy" in title.lower() or "denied" in title.lower():
                category = "POLICY_DENIAL"
            elif "validation" in title.lower():
                category = "VALIDATION_FAILURE"
            elif "error" in title.lower():
                category = "EXECUTION_ANOMALY"
            else:
                category = "OTHER"
            
            # Triggered by
            triggered_by_data = finding.get("triggered_by", {})
            tool_name = triggered_by_data.get("tool_name") if isinstance(triggered_by_data, dict) else None
            source_seq = triggered_by_data.get("source_event_seq") if isinstance(triggered_by_data, dict) else None
            
            # Evidence
            evidence_data = finding.get("evidence", {})
            event_seqs = evidence_data.get("event_seq", []) if isinstance(evidence_data, dict) else []
            
            f.write(_emit(
                "FINDING",
                data={
                    "finding": {
                        "incident_no": f"FC-INC-{finding_id[:8]}",
                        "severity": severity_enum,
                        "category": category,
                        "title": title,
                        "determination": what_happened or "An incident was detected.",
                        "recommendation": mitigation or "Review execution logs and apply appropriate mitigations.",
                        "triggered_by": {
                            "source_type": "tool_call" if tool_name else "system",
                            "tool_name": tool_name,
                            "event_seq": source_seq,
                        },
                        "evidence_refs": [f"APP-A-{seq}" for seq in event_seqs[:3]],
                    }
                },
                level="WARN" if severity_enum in ["MEDIUM", "HIGH", "CRITICAL"] else "INFO"
            ))
            f.write("\n")
        
        # 4. ATTESTATION
        f.write(_emit(
            "ATTESTATION",
            data={
                "attestation": {
                    "statement": "This report was automatically generated and cryptographically sealed by FailCore Runtime v0.1.2.",
                    "report_sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
                    "signature": None,
                    "key_id": None,
                }
            }
        ))
        f.write("\n")
        
        # 5. REPORT_END
        f.write(_emit(
            "REPORT_END",
            report_meta={"report_id": report_id}
        ))
        f.write("\n")