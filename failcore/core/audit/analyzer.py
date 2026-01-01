# failcore/core/audit/analyzer.py
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from failcore.core.audit.model import (
    AuditReport,
    Summary,
    Finding,
    TriggeredBy,
    EvidenceRefs,
    make_snapshot,
    hash_args_best_effort,
    utc_now_iso,
)
from failcore.core.audit.taxonomy import risks_best_effort, risk_codes


# ----------------------------
# Trace helpers
# ----------------------------

def _get_event_type(evt: Dict[str, Any]) -> str:
    if not evt:
        return ""
    for k in ("type", "event_type", "name", "eventType"):
        v = evt.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _get_step_id(evt: Dict[str, Any]) -> Optional[str]:
    step = evt.get("step")
    if isinstance(step, dict):
        sid = step.get("id")
        if isinstance(sid, str) and sid:
            return sid
    for k in ("step_id", "stepId", "stepID"):
        sid = evt.get(k)
        if isinstance(sid, str) and sid:
            return sid
    return None


def _get_tool_name(evt: Dict[str, Any]) -> Optional[str]:
    step = evt.get("step")
    if isinstance(step, dict):
        t = step.get("tool")
        if isinstance(t, str) and t:
            return t
    t = evt.get("tool")
    if isinstance(t, str) and t:
        return t
    return None


def _safe_str(x: Any, limit: int = 600) -> str:
    try:
        s = str(x)
    except Exception:
        s = "<unprintable>"
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def _normalize_ts(ts_any: Any) -> str:
    """
    Normalize timestamps to audit-safe ISO8601 UTC with 'Z' suffix.
    """
    if isinstance(ts_any, str):
        s = ts_any.strip()
        if s.endswith("+00:00"):
            return s.replace("+00:00", "Z")
        return s

    if isinstance(ts_any, (int, float)):
        try:
            return (
                datetime.fromtimestamp(float(ts_any), tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except Exception:
            return utc_now_iso()

    if isinstance(ts_any, datetime):
        dt = ts_any
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (
            dt.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    return utc_now_iso()


# ----------------------------
# Extractors (support v0.1.2 data.* as well)
# ----------------------------

def _extract_policy_info(
    evt: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Returns: policy_id, rule_id, rule_name, decision, reason
    Supports:
      - evt["policy"]
      - evt["data"]["policy"]   (common in v0.1.2)
    """
    policy = None

    # direct
    for k in ("policy", "policy_info", "policyDecision", "policy_decision"):
        v = evt.get(k)
        if isinstance(v, dict):
            policy = v
            break

    # v0.1.2 style: data.policy
    if not policy:
        data = evt.get("data")
        if isinstance(data, dict):
            v = data.get("policy")
            if isinstance(v, dict):
                policy = v

    if not policy:
        return None, None, None, None, None

    policy_id = policy.get("policy_id") or policy.get("id")
    rule_id = policy.get("rule_id") or policy.get("ruleId")
    rule_name = policy.get("rule_name") or policy.get("ruleName")
    decision = policy.get("decision")
    reason = policy.get("reason")

    return (
        str(policy_id) if policy_id is not None else None,
        str(rule_id) if rule_id is not None else None,
        str(rule_name) if rule_name is not None else None,
        str(decision) if decision is not None else None,
        str(reason) if reason is not None else None,
    )


def _extract_validation_info(evt: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns: check_id, decision, reason
    Supports:
      - evt["validation"]
      - evt["data"]["validation"] (common)
    """
    vinfo = None

    for k in ("validation", "validation_info", "validationInfo"):
        v = evt.get(k)
        if isinstance(v, dict):
            vinfo = v
            break

    if not vinfo:
        data = evt.get("data")
        if isinstance(data, dict):
            v = data.get("validation")
            if isinstance(v, dict):
                vinfo = v

    if not vinfo:
        return None, None, None

    check_id = vinfo.get("check_id") or vinfo.get("checkId")
    decision = vinfo.get("decision")
    reason = vinfo.get("reason")
    return (
        str(check_id) if check_id is not None else None,
        str(decision) if decision is not None else None,
        str(reason) if reason is not None else None,
    )


def _extract_error_blob(evt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = evt.get("result")
    if isinstance(r, dict):
        e = r.get("error")
        if isinstance(e, dict):
            return e
    e2 = evt.get("error")
    if isinstance(e2, dict):
        return e2
    return None


def _should_emit_finding(event_type: str, level: str, severity: str = "", status: str = "") -> bool:
    et = (event_type or "").upper()
    lv = (level or "").upper()
    sev = (severity or "").upper()
    st = (status or "").upper()
    
    if "POLICY_DENIED" in et:
        return True
    if "VALIDATION_FAILED" in et:
        return True
    if lv == "ERROR":
        return True
    # Critical: Also detect BLOCKED events (severity="block" or status="BLOCKED")
    if sev == "BLOCK" or "BLOCK" in st:
        return True
    return False


def _base_severity_from_event(event_type: str, level: str, severity: str = "", status: str = "") -> str:
    et = (event_type or "").upper()
    lv = (level or "").upper()
    sev = (severity or "").upper()
    st = (status or "").upper()
    
    # Critical: BLOCKED events are HIGH severity (runtime enforcement)
    if sev == "BLOCK" or "BLOCK" in st:
        return "HIGH"
    if "POLICY_DENIED" in et or "DENIED" in et:
        return "HIGH"
    if "VALIDATION_FAILED" in et:
        return "MED"
    if lv == "ERROR":
        return "MED"
    if lv == "WARN":
        return "LOW"
    return "LOW"


def _upgrade_severity_by_owasp(base: str, owasp_ids: List[str]) -> str:
    crit_set = {"ASI05", "ASI01", "ASI03"}
    if any(x in crit_set for x in owasp_ids):
        return "CRIT"
    return base


def _severity_rank(sev: str) -> int:
    return {"CRIT": 4, "HIGH": 3, "MED": 2, "LOW": 1}.get(sev.upper(), 0)


def _select_evidence_seqs(current_seq: Any, recent_seqs: Optional[List[int]]) -> List[int]:
    out: List[int] = []
    if isinstance(current_seq, int):
        out.append(current_seq)
    else:
        try:
            if current_seq is not None:
                out.append(int(current_seq))
        except Exception:
            pass

    if recent_seqs:
        for s in recent_seqs[-3:]:
            if isinstance(s, int) and s not in out:
                out.append(s)

    out = sorted(set(out))
    return out


def _best_effort_arg_hash(body: Dict[str, Any]) -> Optional[str]:
    step = body.get("step")
    if isinstance(step, dict):
        meta = step.get("metadata")
        if isinstance(meta, dict) and meta:
            return hash_args_best_effort(meta)

    payload = body.get("input") or body.get("payload") or body.get("args") or None
    return hash_args_best_effort(payload)


def _build_triggered_by(
    *,
    etype: str,
    tool_name: Optional[str],
    step_start_event: Optional[Dict[str, Any]],
) -> Optional[TriggeredBy]:
    if tool_name or step_start_event:
        seq = None
        if isinstance(step_start_event, dict):
            seq = step_start_event.get("seq")
        return TriggeredBy(
            source_type="tool_call",
            source_event_seq=seq if isinstance(seq, int) else None,
            notes=f"best-effort link from {etype} to STEP_START" if step_start_event else "best-effort tool linkage",
            tool_name=tool_name,
        )
    return None


def _build_snapshot(
    etype: str,
    body: Dict[str, Any],
    *,
    reason: Optional[str],
    v_reason: Optional[str],
    err_blob: Optional[Dict[str, Any]],
) -> Optional[Any]:
    msg = reason or v_reason
    err = _safe_str(err_blob) if err_blob else None

    input_excerpt = None
    output_excerpt = None

    if msg:
        input_excerpt = f"{etype}: {msg}"
    elif err:
        input_excerpt = f"{etype}: {err}"

    policy = body.get("policy")
    if not isinstance(policy, dict):
        data = body.get("data")
        if isinstance(data, dict) and isinstance(data.get("policy"), dict):
            policy = data.get("policy")

    if isinstance(policy, dict):
        output_excerpt = _safe_str(
            {
                "decision": policy.get("decision"),
                "rule_id": policy.get("rule_id") or policy.get("ruleId"),
                "code": policy.get("code"),
            },
            limit=400,
        )
    else:
        result = body.get("result")
        if isinstance(result, dict):
            output_excerpt = _safe_str(
                {
                    "status": result.get("status"),
                    "phase": result.get("phase"),
                    "severity": result.get("severity"),
                    "error": result.get("error"),
                },
                limit=400,
            )

    if not input_excerpt and not output_excerpt:
        return None

    return make_snapshot(
        input_text=input_excerpt,
        output_text=output_excerpt,
        notes="post-mortem snapshot (redacted, truncated)",
    )


def _default_mitigation(*, rule_id: Optional[str], etype: str, owasp_ids: List[str]) -> str:
    if rule_id:
        return f"Review policy rule '{rule_id}' and tighten allowlists/constraints to prevent recurrence."
    if "POLICY_DENIED" in (etype or "").upper():
        return "Review policy configuration and confirm the action should be denied for this tool/context."
    if owasp_ids:
        return f"Investigate mapped OWASP Agentic risks ({', '.join(owasp_ids)}) and apply least-privilege constraints."
    return "Review execution constraints and add appropriate validation/policy guards."


def _build_titles(
    *,
    etype: str,
    level: str,
    rule_id: Optional[str],
    rule_name: Optional[str],
    reason: Optional[str],
    v_reason: Optional[str],
    err_blob: Optional[Dict[str, Any]],
    severity: str = "",
    status: str = "",
) -> Tuple[str, str]:
    et = etype or "EVENT"
    sev = (severity or "").upper()
    st = (status or "").upper()
    
    # Critical: Handle BLOCKED events (runtime enforcement)
    if sev == "BLOCK" or "BLOCK" in st:
        error_code = err_blob.get("code", "") if err_blob else ""
        error_msg = err_blob.get("message", "") if err_blob else ""
        if error_code:
            return f"Runtime enforcement blocked: {error_code}", (error_msg or "Operation was blocked by FailCore runtime enforcement.")
        return "Runtime enforcement blocked unsafe execution", (error_msg or "Operation was blocked by FailCore runtime enforcement.")
    
    if "POLICY_DENIED" in et.upper():
        details = reason or "Policy decision denied the step."
        if rule_name:
            return f"Policy denied: {rule_name}", details
        if rule_id:
            return f"Policy denied ({rule_id})", details
        return "Policy denied unsafe execution", details

    if "VALIDATION_FAILED" in et.upper():
        return "Validation failed", (v_reason or reason or "Validation decision denied the step.")

    if (level or "").upper() == "ERROR":
        return "Execution error", (_safe_str(err_blob) if err_blob else (reason or "Execution failed."))

    return f"Finding: {et}", (reason or v_reason or "An event was flagged as a finding.")


# ----------------------------
# Main analyzer
# ----------------------------

def analyze_events(
    events: List[Dict[str, Any]],
    *,
    trace_path: Optional[str] = None,
) -> AuditReport:
    run_id = _extract_run_id(events) or None

    step_start_by_step: Dict[str, Dict[str, Any]] = {}
    last_tool_name_by_step: Dict[str, str] = {}
    recent_seq_by_step: Dict[str, List[int]] = {}

    summary = Summary(tool_calls=0, denied=0, errors=0, warnings=0, risk_score=None)
    findings: List[Finding] = []

    for ev in events:
        seq = ev.get("seq")
        level = (ev.get("level") or "").upper()

        body = ev.get("event") or {}
        if not isinstance(body, dict):
            body = {"raw": body}

        etype = _get_event_type(body)
        step_id = _get_step_id(body)
        tool_name = _get_tool_name(body)

        ts_norm = _normalize_ts(ev.get("ts"))

        # summary counters
        if etype.upper() == "STEP_START":
            summary = replace(summary, tool_calls=summary.tool_calls + 1)
        if level == "WARN":
            summary = replace(summary, warnings=summary.warnings + 1)
        if level == "ERROR":
            summary = replace(summary, errors=summary.errors + 1)
        if "POLICY_DENIED" in etype.upper():
            summary = replace(summary, denied=summary.denied + 1)
        
        # Critical: Also count BLOCKED events as denied
        severity_val = body.get("severity", "")
        result_data = body.get("data", {}).get("result", {}) if isinstance(body.get("data"), dict) else {}
        status_val = result_data.get("status", "") if isinstance(result_data, dict) else ""
        if (severity_val or "").upper() == "BLOCK" or "BLOCK" in (status_val or "").upper():
            summary = replace(summary, denied=summary.denied + 1)

        # per-step indices
        if step_id:
            recent_seq_by_step.setdefault(step_id, [])
            if isinstance(seq, int):
                recent_seq_by_step[step_id].append(seq)
                if len(recent_seq_by_step[step_id]) > 10:
                    recent_seq_by_step[step_id] = recent_seq_by_step[step_id][-10:]

        if etype.upper() == "STEP_START" and step_id:
            step_start_by_step[step_id] = ev
            if tool_name:
                last_tool_name_by_step[step_id] = tool_name

        # Extract severity and status for blocked event detection
        severity = body.get("severity", "")
        result = body.get("data", {}).get("result", {}) if isinstance(body.get("data"), dict) else {}
        status = result.get("status", "") if isinstance(result, dict) else ""

        # Emit finding?
        if not _should_emit_finding(etype, level, severity, status):
            continue

        policy_id, rule_id, rule_name, decision, reason = _extract_policy_info(body)
        check_id, v_decision, v_reason = _extract_validation_info(body)
        err_blob = _extract_error_blob(body)

        # ------------------------------------------------------
        # Build shared context FIRST (fix NameError in special branch)
        # ------------------------------------------------------
        tool_for_risk = tool_name or (last_tool_name_by_step.get(step_id) if step_id else None)

        risks = risks_best_effort(
            rule_id=rule_id,
            event_name=etype,
            message=reason or v_reason or _safe_str(err_blob),
            tool_name=tool_for_risk,
        )
        owasp_ids = risk_codes(risks)

        trig = _build_triggered_by(
            etype=etype,
            tool_name=tool_for_risk,
            step_start_event=step_start_by_step.get(step_id) if step_id else None,
        )

        evidence = EvidenceRefs(
            trace_path=trace_path,
            event_seq=_select_evidence_seqs(seq, recent_seq_by_step.get(step_id) if step_id else None),
            arg_hash=_best_effort_arg_hash(body),
            output_hash=None,
        )

        snapshot = _build_snapshot(etype, body, reason=reason, v_reason=v_reason, err_blob=err_blob)

        reproducible: Optional[bool] = None
        if snapshot is not None or evidence.arg_hash is not None:
            reproducible = True

        # ======================================================
        # SPECIAL CASE: POLICY_DENIED (audit-grade handling)
        # ======================================================
        if "POLICY_DENIED" in etype.upper():
            tool = tool_for_risk or "unknown-tool"
            rule_label = rule_name or rule_id or "unknown-policy"

            title = "Policy denied unsafe tool execution"

            if reason:
                what = (
                    f"Tool '{tool}' was denied by policy rule '{rule_label}' "
                    f"because {reason}."
                )
            else:
                what = (
                    f"Tool '{tool}' was denied by policy rule '{rule_label}' "
                    f"due to a policy violation."
                )

            owasp_ids = owasp_ids or ["ASI03"]  # Tool Misuse

            base = "HIGH"
            severity = _upgrade_severity_by_owasp(base, owasp_ids)

            mitigation = (
                f"Review policy rule '{rule_label}' and restrict tool '{tool}' "
                f"to least-privilege access. Consider adding explicit allowlists "
                f"or stronger precondition validation."
            )

            findings.append(
                Finding(
                    finding_id=str(uuid.uuid4()),
                    ts=ts_norm,
                    severity=severity,
                    title=title,
                    what_happened=what,
                    rule_id=rule_id,
                    rule_name=rule_name,
                    owasp_agentic_ids=owasp_ids,
                    triggered_by=trig,
                    evidence=evidence,
                    snapshot=snapshot,
                    reproducible=reproducible,
                    mitigation=mitigation,
                    tags=["policy", "security", "interception"],
                )
            )
            continue

        # Generic handling
        mitigation = _default_mitigation(rule_id=rule_id, etype=etype, owasp_ids=owasp_ids)

        title, what = _build_titles(
            etype=etype,
            level=level,
            rule_id=rule_id,
            rule_name=rule_name,
            reason=reason,
            v_reason=v_reason,
            err_blob=err_blob,
            severity=severity,
            status=status,
        )

        base_sev = _base_severity_from_event(etype, level, severity, status)
        sev = _upgrade_severity_by_owasp(base_sev, owasp_ids)

        findings.append(
            Finding(
                finding_id=str(uuid.uuid4()),
                ts=ts_norm,
                severity=sev,
                title=title,
                what_happened=what,
                rule_id=rule_id,
                rule_name=rule_name,
                owasp_agentic_ids=owasp_ids,
                triggered_by=trig,
                evidence=evidence,
                snapshot=snapshot,
                reproducible=reproducible,
                mitigation=mitigation,
                tags=[],
            )
        )

    # risk_score（简单总分）
    score = sum(
        10 if f.severity == "CRIT" else
        5 if f.severity == "HIGH" else
        2 if f.severity == "MED" else
        1
        for f in findings
    )
    summary = replace(summary, risk_score=score)

    findings.sort(key=lambda f: (_severity_rank(f.severity), f.ts), reverse=True)

    report = AuditReport.new(
        run_id=run_id,
        summary=summary,
        findings=findings,
        metadata={"trace_schema": _extract_trace_schema(events)},
    )
    return report


def _extract_run_id(events: List[Dict[str, Any]]) -> Optional[str]:
    for ev in events:
        run = ev.get("run")
        if isinstance(run, dict):
            rid = run.get("run_id") or run.get("id")
            if isinstance(rid, str) and rid:
                return rid
    for ev in events:
        body = ev.get("event")
        if isinstance(body, dict):
            rid = body.get("run_id") or body.get("runId")
            if isinstance(rid, str) and rid:
                return rid
    return None


def _extract_trace_schema(events: List[Dict[str, Any]]) -> Optional[str]:
    for ev in events:
        s = ev.get("schema")
        if isinstance(s, str) and s:
            return s
    return None
