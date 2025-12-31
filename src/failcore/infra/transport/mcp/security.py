from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


class McpSecurityError(RuntimeError):
    pass


@dataclass
class McpSecurityConfig:
    """
    Minimal MCP protocol-level security guard.

    This is NOT a replacement for FailCore policy engine.
    It's a protocol/adapter sanity layer to mitigate common injection surfaces.
    """

    # Very conservative: block obvious prompt injection patterns inside tool descriptions
    block_injection_patterns: bool = True

    # Block local file paths in args if you want
    block_file_paths: bool = False

    # Block private network urls (ssrf-like) if you want
    block_private_urls: bool = False


_INJECTION_RE = re.compile(
    r"(ignore\s+previous|system\s+prompt|developer\s+message|"
    r"do\s+not\s+follow|jailbreak|prompt\s+injection)",
    re.IGNORECASE,
)

_PRIVATE_URL_RE = re.compile(
    r"(^|\b)(localhost|127\.0\.0\.1|0\.0\.0\.0|169\.254\.169\.254|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)",
    re.IGNORECASE,
)

_WINDOWS_PATH_RE = re.compile(r"^[a-zA-Z]:\\")
_UNIX_PATH_RE = re.compile(r"^/")


class McpSecurity:
    def __init__(self, cfg: Optional[McpSecurityConfig] = None) -> None:
        self._cfg = cfg or McpSecurityConfig()

    def check_tool_descriptor(self, tool: Dict[str, Any]) -> None:
        """
        tool: a raw MCP tool descriptor dict from tools/list
        Best-effort injection scan on description/title/schema.
        """
        if not self._cfg.block_injection_patterns:
            return

        hay: list[str] = []
        for k in ("name", "title", "description"):
            v = tool.get(k)
            if isinstance(v, str):
                hay.append(v)

        # Some servers embed description inside schema fields
        schema = tool.get("inputSchema") or tool.get("input_schema") or tool.get("schema")
        if isinstance(schema, dict):
            _collect_strings(schema, hay, limit=50)

        joined = "\n".join(hay)
        if _INJECTION_RE.search(joined):
            raise McpSecurityError("tool descriptor looks like prompt-injection content")

    def check_call_args(self, args: Dict[str, Any]) -> None:
        """
        Best-effort scan of user-provided tool args.
        """
        if not (self._cfg.block_file_paths or self._cfg.block_private_urls):
            return

        strings: list[str] = []
        _collect_strings(args, strings, limit=200)

        if self._cfg.block_file_paths:
            for s in strings:
                if _WINDOWS_PATH_RE.match(s) or _UNIX_PATH_RE.match(s):
                    raise McpSecurityError("file path argument blocked by MCP security guard")

        if self._cfg.block_private_urls:
            for s in strings:
                if _PRIVATE_URL_RE.search(s):
                    raise McpSecurityError("private-network url blocked by MCP security guard")


def _collect_strings(obj: Any, out: list[str], *, limit: int) -> None:
    if len(out) >= limit:
        return
    if obj is None:
        return
    if isinstance(obj, str):
        out.append(obj)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if len(out) >= limit:
                return
            _collect_strings(k, out, limit=limit)
            _collect_strings(v, out, limit=limit)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            if len(out) >= limit:
                return
            _collect_strings(v, out, limit=limit)
