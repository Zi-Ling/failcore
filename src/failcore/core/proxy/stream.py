# failcore/core/proxy/stream.py
"""
Stream (SSE) handler: tee + side-channel scanning + evidence emission

Goals:
- Per-stream isolated scan state (no shared mutable globals)
- Strict mode blocks FUTURE chunks (cannot undo already sent bytes)
- Warn mode never blocks forwarding
- Bounded evidence queue (drop evidence, never block stream)
- Conservative decoding + bounded scanning to avoid OOM
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Optional, Dict, Pattern, Iterable
import asyncio


# ----------------------------
# Types
# ----------------------------

class StreamViolation(Exception):
    """Raised when strict mode detects a violation (terminate future chunks)."""
    pass


@dataclass(frozen=True)
class StreamEvidence:
    """
    Evidence emitted by StreamHandler.

    NOTE:
    - This is intentionally JSON-friendly (dict conversion is trivial).
    - Do NOT include raw secrets; include labels only.
    """
    type: str               # e.g. "stream_dlp_hit"
    run_id: str
    step_id: str
    hits: list[str]
    severity: str           # "warning" | "critical"
    source: str = "stream"  # constant tag


# ----------------------------
# Handler
# ----------------------------

class StreamHandler:
    """
    Streaming/SSE response handler.

    Design guarantees:
    - Per-stream isolated scan state
    - Strict mode stops FUTURE chunks (cannot undo already-sent bytes)
    - Warn mode never blocks forwarding
    - Bounded async evidence queue (drop on full)
    - Bounded scan window to avoid unbounded memory growth
    """

    def __init__(
        self,
        *,
        strict_mode: bool = False,
        dlp_patterns: Optional[Dict[str, Pattern[str]]] = None,
        evidence_queue: Optional[asyncio.Queue] = None,
        max_scan_buffer: int = 64 * 1024,   # strict sliding window max
        max_chunk_scan: int = 8 * 1024,     # warn chunk-local scan cap
        decode_errors: str = "ignore",      # "ignore" reduces false positives from partial UTF-8
    ):
        self.strict_mode = bool(strict_mode)
        self.dlp_patterns: Dict[str, Pattern[str]] = dict(dlp_patterns or {})
        self.evidence_queue = evidence_queue
        self.max_scan_buffer = int(max_scan_buffer)
        self.max_chunk_scan = int(max_chunk_scan)
        self.decode_errors = decode_errors

    async def process_stream(
        self,
        upstream_stream: AsyncIterator[bytes],
        *,
        run_id: str,
        step_id: str,
    ) -> AsyncIterator[bytes]:
        """
        Tee streaming response:
        - strict: scan -> then forward
        - warn: forward -> scan (best-effort)
        """
        scan_buffer = bytearray()

        async for chunk in upstream_stream:
            if not chunk:
                continue

            if self.strict_mode:
                # Strict: scan first; if violation -> stop future chunks
                await self._scan_chunk(chunk, scan_buffer, run_id, step_id)
                yield chunk
            else:
                # Warn: forward immediately; scan in side-channel (best-effort)
                yield chunk
                try:
                    await self._scan_chunk(chunk, scan_buffer, run_id, step_id)
                except Exception:
                    # Fail-open: scanner bugs must not break streaming
                    pass

    async def _scan_chunk(
        self,
        chunk: bytes,
        scan_buffer: bytearray,
        run_id: str,
        step_id: str,
    ) -> None:
        """
        Scan chunk for DLP hits.

        - strict: sliding window scan across the stream
        - warn: chunk-local scan (bounded)
        """
        if not self.dlp_patterns:
            return

        text = self._decode_for_scan(chunk, scan_buffer)
        if not text:
            return

        hits = self._find_hits(text)
        if not hits:
            return

        await self._emit_evidence(
            StreamEvidence(
                type="stream_dlp_hit",
                run_id=run_id,
                step_id=step_id,
                hits=hits,
                severity="critical" if self.strict_mode else "warning",
            )
        )

        if self.strict_mode:
            raise StreamViolation(f"DLP violation in stream: {', '.join(hits)}")

    def _decode_for_scan(self, chunk: bytes, scan_buffer: bytearray) -> str:
        """
        Returns decoded text to scan based on mode.

        strict:
          - maintain sliding window buffer (bounded)
          - decode entire window each time (window is bounded)
        warn:
          - decode only a bounded prefix of the chunk
        """
        if self.strict_mode:
            scan_buffer.extend(chunk)
            if self.max_scan_buffer > 0 and len(scan_buffer) > self.max_scan_buffer:
                del scan_buffer[:-self.max_scan_buffer]
            try:
                return scan_buffer.decode("utf-8", errors=self.decode_errors)
            except Exception:
                return ""
        else:
            if self.max_chunk_scan > 0:
                chunk = chunk[: self.max_chunk_scan]
            try:
                return chunk.decode("utf-8", errors=self.decode_errors)
            except Exception:
                return ""

    def _find_hits(self, text: str) -> list[str]:
        """
        Find pattern hits (labels only). Never return matched raw strings.
        """
        hits: list[str] = []
        for name, pattern in self.dlp_patterns.items():
            try:
                if pattern.search(text):
                    hits.append(name)
            except Exception:
                # Bad pattern must not break proxy
                continue
        return hits

    async def _emit_evidence(self, evidence: StreamEvidence) -> None:
        """
        Best-effort evidence emission via bounded queue.
        Drops evidence if queue is full.
        """
        q = self.evidence_queue
        if q is None:
            return

        payload = {
            "type": evidence.type,
            "run_id": evidence.run_id,
            "step_id": evidence.step_id,
            "hits": evidence.hits,
            "severity": evidence.severity,
            "source": evidence.source,
        }

        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop evidence, never block stream
            pass


__all__ = ["StreamHandler", "StreamViolation", "StreamEvidence"]
