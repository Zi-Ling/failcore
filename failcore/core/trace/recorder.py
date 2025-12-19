# failcore/core/trace/recorder.py
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Union


def _default_json_encoder(obj: Any) -> Any:
    """
    Best-effort JSON encoding for trace payloads.
    - dataclasses -> dict
    - datetime -> isoformat
    - Enum -> value
    - fallback -> str(obj)
    """
    # dataclass
    if is_dataclass(obj):
        return asdict(obj)

    # datetime
    if isinstance(obj, datetime):
        return obj.isoformat()

    # Enum
    v = getattr(obj, "value", None)
    if v is not None and not isinstance(obj, (str, bytes, bytearray, dict, list)):
        return v

    # bytes
    if isinstance(obj, (bytes, bytearray)):
        return f"<{len(obj)} bytes>"

    return str(obj)


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


class TraceRecorder:
    """
    Recorder interface.
    """
    def record(self, event: Any) -> None:
        raise NotImplementedError


class NullTraceRecorder(TraceRecorder):
    """
    No-op recorder.
    """
    def record(self, event: Any) -> None:
        return


class JsonlTraceRecorder(TraceRecorder):
    """
    JSONL recorder (one event per line).
    - thread-safe (simple lock)
    - line-buffered (flush each write by default)
    - maintains sequence number per run
    """

    def __init__(
        self,
        path: str,
        *,
        flush: bool = True,
        ensure_ascii: bool = False,
    ) -> None:
        if not path or not isinstance(path, str):
            raise ValueError("path must be a non-empty string")
        self.path = path
        self.flush = flush
        self.ensure_ascii = ensure_ascii

        _ensure_parent_dir(self.path)
        self._lock = threading.Lock()
        self._seq = 0  # Sequence counter for this run

        # Keep file handle open for performance; safe enough for v0.1.
        # If you prefer reopen-per-write, you can change it later.
        self._fp = open(self.path, "a", encoding="utf-8", newline="\n")

    def close(self) -> None:
        with self._lock:
            try:
                self._fp.close()
            except Exception:
                pass
    
    def next_seq(self) -> int:
        """Get next sequence number (thread-safe)"""
        with self._lock:
            self._seq += 1
            return self._seq

    def record(self, event: Any) -> None:
        """
        Convert event -> dict -> json line.
        Event must be TraceEvent with to_dict() method.
        """
        # Only accept TraceEvent
        if hasattr(event, 'to_dict') and callable(getattr(event, 'to_dict')):
            payload = event.to_dict()
        else:
            raise TypeError(f"Event must be TraceEvent with to_dict() method, got {type(event)}")

        line = json.dumps(
            payload,
            ensure_ascii=self.ensure_ascii,
            default=_default_json_encoder,
            separators=(",", ":"),
        )

        with self._lock:
            self._fp.write(line + "\n")
            if self.flush:
                self._fp.flush()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
