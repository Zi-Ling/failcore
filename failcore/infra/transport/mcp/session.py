from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from .codec import JsonRpcCodec, JsonRpcCodecConfig, McpCodecError


class McpSessionError(RuntimeError):
    pass


class McpSessionClosed(McpSessionError):
    pass


class McpProcessCrashed(McpSessionError):
    pass


class McpTimeout(McpSessionError):
    pass


NotificationHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class McpSessionConfig:
    """
    Configuration for a long-lived MCP stdio session.

    command:
        The executable and args, e.g. ["node", "server.js"] or ["python", "-m", "..."].
    cwd:
        Working directory for subprocess.
    env:
        Extra env vars to merge into os.environ.

    codec_mode:
        "ndjson" (Phase 0.7 default) or "content_length" (more standard framing).

    startup_timeout_s:
        Time allowed for process to start.
    request_timeout_s:
        Default timeout for JSON-RPC requests.

    max_restarts:
        Max auto-restarts before giving up.
    restart_backoff_s:
        Base backoff for restarts (exponential-ish).
    serialize_requests:
        If True, serialize requests at session level (recommended for stdio).
    """

    command: list[str]
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None

    codec_mode: str = "ndjson"  # "ndjson" | "content_length"
    max_message_bytes: int = 8 * 1024 * 1024

    startup_timeout_s: float = 10.0
    request_timeout_s: float = 60.0

    max_restarts: int = 3
    restart_backoff_s: float = 0.5

    serialize_requests: bool = True


class McpSession:
    """
    A long-lived MCP stdio session that speaks JSON-RPC 2.0.

    Improvements over Phase 0.7 draft:
      - Framing via JsonRpcCodec (ndjson or content-length)
      - Chunk-based reader loop (supports any framing)
      - Optional notification handler for server->client messages
    """

    def __init__(self, cfg: McpSessionConfig, *, on_notification: Optional[NotificationHandler] = None) -> None:
        self._cfg = cfg
        self._codec = JsonRpcCodec(
            JsonRpcCodecConfig(mode=cfg.codec_mode, max_message_bytes=cfg.max_message_bytes)
        )
        self._on_notification = on_notification

        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task[None]] = None

        self._pending: Dict[int, asyncio.Future[Any]] = {}
        self._next_id: int = 1

        self._closed: bool = False
        self._restart_count: int = 0

        # Prevent concurrent writes that could interleave on stdin
        self._write_lock = asyncio.Lock()

        # Optional: serialize request/response semantics for fragile backends
        self._call_lock = asyncio.Lock()

        # Used to signal crash to callers
        self._crash_event = asyncio.Event()
        self._crash_waiter_task: Optional[asyncio.Task[bool]] = None

    # =========================================================
    # Lifecycle
    # =========================================================

    async def start(self) -> None:
        """
        Ensure the session process is running.
        Safe to call multiple times.
        """
        if self._closed:
            raise McpSessionClosed("MCP session is closed")

        if self._proc and self._proc.returncode is None:
            return

        await self._spawn_process()

    async def shutdown(self) -> None:
        """
        Stop session and terminate process.
        """
        self._closed = True
        await self._terminate_process()
        self._fail_all_pending(McpSessionClosed("session shutdown"))

    # =========================================================
    # Public JSON-RPC call
    # =========================================================

    async def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout_s: Optional[float] = None,
    ) -> Any:
        """
        Perform a JSON-RPC request and return the 'result'.
        """
        if self._closed:
            raise McpSessionClosed("MCP session is closed")

        await self.start()

        if self._cfg.serialize_requests:
            async with self._call_lock:
                return await self._call_inner(method, params, timeout_s=timeout_s)
        return await self._call_inner(method, params, timeout_s=timeout_s)

    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a JSON-RPC notification (no response expected).
        """
        if self._closed:
            raise McpSessionClosed("MCP session is closed")

        await self.start()

        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        await self._send_msg(msg)

    # =========================================================
    # Internal call implementation
    # =========================================================

    async def _call_inner(
        self,
        method: str,
        params: Optional[Dict[str, Any]],
        *,
        timeout_s: Optional[float],
    ) -> Any:
        if self._crash_event.is_set():
            await self._maybe_restart_or_raise()

        req_id = self._alloc_id()
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut

        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        try:
            await self._send_msg(msg)

            t = timeout_s if timeout_s is not None else self._cfg.request_timeout_s
            try:
                return await asyncio.wait_for(self._wait_future_or_crash(fut), timeout=t)
            except asyncio.TimeoutError:
                self._pending.pop(req_id, None)
                if not fut.done():
                    fut.cancel()
                raise McpTimeout(f"timeout calling {method} after {t:.1f}s")
        except Exception:
            self._pending.pop(req_id, None)
            if not fut.done():
                fut.cancel()
            raise

    async def _wait_future_or_crash(self, fut: asyncio.Future[Any]) -> Any:
        """
        Wait for the response future, but if the process crashes first, raise.
        Avoids per-call task leaks by reusing a crash waiter task.
        """
        crash_task = self._get_crash_waiter_task()
        done, _ = await asyncio.wait([fut, crash_task], return_when=asyncio.FIRST_COMPLETED)

        if fut in done:
            return fut.result()

        raise McpProcessCrashed("MCP process crashed during request")

    def _get_crash_waiter_task(self) -> asyncio.Task[bool]:
        if self._crash_waiter_task is None or self._crash_waiter_task.done():
            self._crash_waiter_task = asyncio.create_task(self._crash_event.wait())
        return self._crash_waiter_task

    # =========================================================
    # Process management
    # =========================================================

    async def _spawn_process(self) -> None:
        await self._terminate_process()

        env = os.environ.copy()
        if self._cfg.env:
            env.update(self._cfg.env)

        self._proc = await asyncio.create_subprocess_exec(
            *self._cfg.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cfg.cwd,
            env=env,
        )

        self._crash_event.clear()

        # Reset codec buffer/state on restart
        self._codec = JsonRpcCodec(
            JsonRpcCodecConfig(mode=self._cfg.codec_mode, max_message_bytes=self._cfg.max_message_bytes)
        )

        self._reader_task = asyncio.create_task(self._reader_loop())

        try:
            await asyncio.wait_for(self._ensure_running(), timeout=self._cfg.startup_timeout_s)
        except asyncio.TimeoutError:
            await self._terminate_process()
            raise McpSessionError("MCP process failed to start within startup_timeout_s")

    async def _ensure_running(self) -> None:
        assert self._proc is not None
        await asyncio.sleep(0.05)
        if self._proc.returncode is not None:
            raise McpSessionError(f"MCP process exited early with code {self._proc.returncode}")

    async def _terminate_process(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except Exception:
                pass
            self._reader_task = None

        if self._proc is None:
            return

        proc = self._proc
        self._proc = None

        if proc.returncode is not None:
            return

        try:
            if sys.platform.startswith("win"):
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            return

        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except Exception:
                pass

    async def _maybe_restart_or_raise(self) -> None:
        if self._closed:
            raise McpSessionClosed("MCP session is closed")

        if self._restart_count >= self._cfg.max_restarts:
            raise McpProcessCrashed(
                f"MCP process crashed and exceeded max_restarts={self._cfg.max_restarts}"
            )

        self._restart_count += 1
        backoff = self._cfg.restart_backoff_s * (2 ** (self._restart_count - 1))
        await asyncio.sleep(backoff)

        self._fail_all_pending(McpProcessCrashed("MCP process crashed (auto-restart)"))
        await self._spawn_process()

    def _fail_all_pending(self, exc: Exception) -> None:
        pending = list(self._pending.items())
        self._pending.clear()
        for _id, fut in pending:
            if not fut.done():
                fut.set_exception(exc)

    # =========================================================
    # JSON-RPC send/receive (codec-based)
    # =========================================================

    async def _send_msg(self, msg: Dict[str, Any]) -> None:
        if self._proc is None or self._proc.returncode is not None:
            self._crash_event.set()
            await self._maybe_restart_or_raise()

        assert self._proc is not None
        assert self._proc.stdin is not None

        try:
            data = self._codec.encode(msg)
        except Exception as e:
            raise McpSessionError(f"failed to encode json-rpc message: {e}") from e

        async with self._write_lock:
            try:
                self._proc.stdin.write(data)
                await self._proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                self._crash_event.set()
                await self._maybe_restart_or_raise()
            except Exception as e:
                raise McpSessionError(f"failed to write to MCP stdin: {e}") from e

    async def _reader_loop(self) -> None:
        """
        Chunk-based reader loop:
          - read stdout in chunks
          - decode messages via codec.feed()
          - route responses (id present) to pending futures
          - route notifications (no id) to on_notification
        """
        assert self._proc is not None
        assert self._proc.stdout is not None

        try:
            while True:
                chunk = await self._proc.stdout.read(4096)
                if not chunk:
                    break

                try:
                    msgs = self._codec.feed(chunk)
                except McpCodecError as e:
                    # Protocol framing error -> treat as crash-ish
                    raise McpSessionError(f"codec decode error: {e}") from e

                for msg in msgs:
                    await self._handle_msg(msg)

        except asyncio.CancelledError:
            return
        except Exception:
            # unexpected reader failure
            pass
        finally:
            self._crash_event.set()
            self._fail_all_pending(McpProcessCrashed("MCP reader loop terminated"))

    async def _handle_msg(self, msg: Dict[str, Any]) -> None:
        # Response has "id"
        if "id" in msg:
            req_id = msg.get("id")
            fut = self._pending.pop(req_id, None)
            if fut is None:
                return

            if msg.get("error") is not None:
                if not fut.done():
                    fut.set_exception(McpSessionError(str(msg["error"])))
            else:
                if not fut.done():
                    fut.set_result(msg.get("result"))
            return

        # Notification: no id, has method
        if "method" in msg:
            if self._on_notification is not None:
                try:
                    await self._on_notification(msg)
                except Exception:
                    # Notification handler should never crash the session
                    return
            return

        # Unknown message shape: ignore
        return

    def _alloc_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid
