# failcore/infra/forensics/writer.py
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
    Write forensic audit report to a JSON file.

    Args:
      report:
        - ForensicReport (dataclass with .to_dict()) OR a plain dict
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
    Dump forensic audit report to a JSON string (for tests/debug).
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
