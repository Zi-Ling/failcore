from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal


class McpCodecError(RuntimeError):
    pass


FrameMode = Literal["ndjson", "content_length"]


@dataclass
class JsonRpcCodecConfig:
    """
    Codec configuration.

    mode:
      - "ndjson": one JSON message per line (newline delimited)
      - "content_length": LSP-style headers:
            Content-Length: <n>\r\n
            \r\n
            <n bytes JSON payload>

    max_message_bytes:
      Safety limit against unbounded memory usage if a peer misbehaves.
    """

    mode: FrameMode = "ndjson"
    max_message_bytes: int = 8 * 1024 * 1024  # 8MB


class JsonRpcCodec:
    """
    Incremental JSON-RPC codec with framing.

    Usage:
        codec = JsonRpcCodec(JsonRpcCodecConfig(mode="ndjson"))
        data = codec.encode({"jsonrpc":"2.0","id":1,"method":"ping","params":{}})
        msgs = codec.feed(stdout_bytes_chunk)

    Notes:
      - This codec only handles framing + JSON parsing.
      - It does NOT validate JSON-RPC semantics (id types, fields, etc.).
    """

    def __init__(self, cfg: Optional[JsonRpcCodecConfig] = None) -> None:
        self._cfg = cfg or JsonRpcCodecConfig()
        self._buf = bytearray()

        # For content_length mode parsing state
        self._expected_len: Optional[int] = None

    # =========================================================
    # Encode
    # =========================================================

    def encode(self, msg: Dict[str, Any]) -> bytes:
        """
        Encode a JSON-RPC message into framed bytes.
        """
        payload = json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        if len(payload) > self._cfg.max_message_bytes:
            raise McpCodecError(f"message too large to encode: {len(payload)} bytes")

        if self._cfg.mode == "ndjson":
            return payload + b"\n"

        if self._cfg.mode == "content_length":
            header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
            return header + payload

        raise McpCodecError(f"unknown codec mode: {self._cfg.mode}")

    # =========================================================
    # Decode (incremental)
    # =========================================================

    def feed(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Feed raw bytes and return any fully decoded JSON messages.
        """
        if not data:
            return []

        self._buf.extend(data)
        if len(self._buf) > self._cfg.max_message_bytes:
            # Not perfect (buffer may include multiple messages), but prevents runaway memory.
            raise McpCodecError(f"buffer exceeded max_message_bytes={self._cfg.max_message_bytes}")

        if self._cfg.mode == "ndjson":
            return self._feed_ndjson()

        if self._cfg.mode == "content_length":
            return self._feed_content_length()

        raise McpCodecError(f"unknown codec mode: {self._cfg.mode}")

    # -------------------------
    # NDJSON mode
    # -------------------------

    def _feed_ndjson(self) -> List[Dict[str, Any]]:
        """
        Parse newline-delimited JSON objects.
        """
        out: List[Dict[str, Any]] = []

        while True:
            nl = self._buf.find(b"\n")
            if nl < 0:
                break

            line = bytes(self._buf[:nl]).strip()
            del self._buf[: nl + 1]

            if not line:
                continue

            try:
                obj = json.loads(line.decode("utf-8"))
            except Exception as e:
                # If peer emits non-JSON lines, treat as protocol error.
                # You may choose to ignore instead; we fail-fast by default.
                raise McpCodecError(f"invalid ndjson line: {e}") from e

            if not isinstance(obj, dict):
                raise McpCodecError("ndjson message must be a JSON object")
            out.append(obj)

        return out

    # -------------------------
    # Content-Length mode
    # -------------------------

    def _feed_content_length(self) -> List[Dict[str, Any]]:
        """
        Parse LSP-style Content-Length framing.
        """
        out: List[Dict[str, Any]] = []

        while True:
            # Step 1: read header (until \r\n\r\n) if we don't know expected length
            if self._expected_len is None:
                header_end = self._find_header_end()
                if header_end is None:
                    break  # need more data

                header_bytes = bytes(self._buf[:header_end])
                del self._buf[: header_end + 4]  # remove header + \r\n\r\n

                expected = self._parse_content_length(header_bytes)
                if expected <= 0:
                    raise McpCodecError(f"invalid Content-Length: {expected}")
                if expected > self._cfg.max_message_bytes:
                    raise McpCodecError(f"Content-Length too large: {expected} > {self._cfg.max_message_bytes}")

                self._expected_len = expected

            # Step 2: read payload of _expected_len
            assert self._expected_len is not None
            if len(self._buf) < self._expected_len:
                break  # need more data

            payload = bytes(self._buf[: self._expected_len])
            del self._buf[: self._expected_len]
            self._expected_len = None

            try:
                obj = json.loads(payload.decode("utf-8"))
            except Exception as e:
                raise McpCodecError(f"invalid JSON payload: {e}") from e

            if not isinstance(obj, dict):
                raise McpCodecError("content_length message must be a JSON object")
            out.append(obj)

        return out

    def _find_header_end(self) -> Optional[int]:
        """
        Find index of b'\\r\\n\\r\\n' in buffer.
        Return the starting index of the delimiter, or None if not found.
        """
        idx = self._buf.find(b"\r\n\r\n")
        if idx < 0:
            return None
        return idx

    def _parse_content_length(self, header: bytes) -> int:
        """
        Parse Content-Length from header bytes.
        Accepts ASCII header lines.
        """
        try:
            text = header.decode("ascii", errors="strict")
        except Exception as e:
            raise McpCodecError(f"header is not ASCII: {e}") from e

        lines = [ln.strip() for ln in text.split("\r\n") if ln.strip()]
        content_length: Optional[int] = None

        for ln in lines:
            # Typical: "Content-Length: 123"
            if ln.lower().startswith("content-length:"):
                _, val = ln.split(":", 1)
                val = val.strip()
                try:
                    content_length = int(val)
                except ValueError as e:
                    raise McpCodecError(f"invalid Content-Length value: {val}") from e

        if content_length is None:
            raise McpCodecError("missing Content-Length header")

        return content_length
