# failcore/cli/commands/service_cmd.py
"""
Service command - Manage FailCore services (proxy + UI) as background processes.

Fixes included:
1) Windows: NO blank console windows on background start
   - Uses pythonw.exe when available
   - Uses CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP
2) Windows GBK UnicodeEncodeError in redirected output
   - Forces UTF-8 for child process via env (PYTHONUTF8 / PYTHONIOENCODING)
3) Logs:
   - Logs live under .failcore/logs/service/
   - proxy.log / ui.log filenames stay stable
   - Adds a "START" banner line with timestamp to each log at launch
4) Robust stop:
   - kill_process_group first (tree/group), fallback kill_process
5) Stale PID cleanup + stable cwd (FailCore root)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Tuple

from failcore.utils.paths import get_failcore_root
from failcore.utils.process import (
    pid_exists,
    kill_process,
    kill_process_group,
    get_process_group_creation_flags,
)

# ---------------------------------------------------------------------
# Paths / defaults
# ---------------------------------------------------------------------

FAILCORE_ROOT = get_failcore_root()

SERVICE_DIR = FAILCORE_ROOT / "service"              # control plane: pid + manifest
LOG_DIR = FAILCORE_ROOT / "logs" / "service"         # data plane: logs

PROXY_PID_FILE = SERVICE_DIR / "proxy.pid"
UI_PID_FILE = SERVICE_DIR / "ui.pid"

PROXY_LOG_FILE = LOG_DIR / "proxy.log"
UI_LOG_FILE = LOG_DIR / "ui.log"

SERVICE_INFO_FILE = SERVICE_DIR / "service.json"

DEFAULT_PROXY_PORT = 8000
DEFAULT_UI_PORT = 8765


# ---------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------

@dataclass
class ServiceInfo:
    proxy: Dict[str, object]
    ui: Dict[str, object]

    @staticmethod
    def empty() -> "ServiceInfo":
        return ServiceInfo(
            proxy={"pid": None, "listen": None, "log_file": str(PROXY_LOG_FILE.relative_to(FAILCORE_ROOT).as_posix()), "started_at": None},
            ui={"pid": None, "host": None, "port": None, "log_file": str(UI_LOG_FILE.relative_to(FAILCORE_ROOT).as_posix()), "started_at": None},
        )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _read_pid(pid_file: Path) -> Optional[int]:
    try:
        if not pid_file.exists():
            return None
        txt = pid_file.read_text(encoding="utf-8").strip()
        if not txt:
            return None
        return int(txt)
    except Exception:
        return None


def _write_pid(pid_file: Path, pid: int) -> None:
    pid_file.write_text(str(pid), encoding="utf-8")


def _remove_file_silent(p: Path) -> None:
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _timestamp() -> str:
    """Get current timestamp in format [YYYY-MM-DD HH:MM:SS]"""
    return time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime())


def _append_log_banner(log_file: Path, name: str, extra: Optional[str] = None) -> None:
    """
    Append a startup banner into the log file.
    We can't reliably prepend timestamps to every child process line without changing their logging,
    but we CAN (a) force UTF-8 and (b) add a clear per-launch boundary here.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write(f"===== START {name.upper()} { _now_iso() } =====\n")
            if extra:
                f.write(f"{extra}\n")
    except Exception:
        pass


def _default_child_env() -> dict:
    """
    Ensure redirected output won't crash on Windows default encodings (GBK).
    Also makes logs consistently UTF-8 everywhere.
    """
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


class TimestampedLogWriter:
    """
    Writes subprocess output to log file with timestamps on each line.
    Runs in a background thread to read from subprocess pipe.
    """
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.file_handle = open(log_file, "a", encoding="utf-8")
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
    
    def start(self, pipe):
        """Start background thread to read from pipe and write with timestamps"""
        def _writer():
            try:
                while not self.stop_event.is_set():
                    line = pipe.readline()
                    if not line:
                        break
                    # Decode if bytes, strip trailing newline
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.rstrip("\n\r")
                    if line:  # Only write non-empty lines
                        timestamped = f"{_timestamp()} {line}\n"
                        self.file_handle.write(timestamped)
                        self.file_handle.flush()
            except Exception:
                pass
            finally:
                try:
                    self.file_handle.flush()
                except Exception:
                    pass
        
        self.thread = threading.Thread(target=_writer, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the writer thread and close file"""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        try:
            self.file_handle.flush()
            self.file_handle.close()
        except Exception:
            pass


# ---------------------------------------------------------------------
# ServiceManager
# ---------------------------------------------------------------------

class ServiceManager:
    """Manages FailCore services (proxy + UI) as background processes."""

    def __init__(self):
        SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ----------------------------
    # Info persistence (optional)
    # ----------------------------

    def _load_info(self) -> ServiceInfo:
        if SERVICE_INFO_FILE.exists():
            try:
                data = json.loads(SERVICE_INFO_FILE.read_text(encoding="utf-8"))
                proxy = data.get("proxy", {}) if isinstance(data, dict) else {}
                ui = data.get("ui", {}) if isinstance(data, dict) else {}
                base = ServiceInfo.empty()
                base.proxy.update(proxy)
                base.ui.update(ui)
                return base
            except Exception:
                pass
        return ServiceInfo.empty()

    def _save_info(self, info: ServiceInfo) -> None:
        try:
            SERVICE_INFO_FILE.write_text(json.dumps(asdict(info), indent=2), encoding="utf-8")
        except Exception:
            pass

    # ----------------------------
    # Running checks (with stale cleanup)
    # ----------------------------

    def _is_running(self, pid_file: Path) -> bool:
        pid = _read_pid(pid_file)
        if pid is None:
            return False
        if pid_exists(pid):
            return True
        _remove_file_silent(pid_file)  # stale PID file
        return False

    def is_proxy_running(self) -> bool:
        return self._is_running(PROXY_PID_FILE)

    def is_ui_running(self) -> bool:
        return self._is_running(UI_PID_FILE)

    def get_proxy_pid(self) -> Optional[int]:
        return _read_pid(PROXY_PID_FILE) if self.is_proxy_running() else None

    def get_ui_pid(self) -> Optional[int]:
        return _read_pid(UI_PID_FILE) if self.is_ui_running() else None

    # ----------------------------
    # Python executable selection (Windows)
    # ----------------------------

    def _get_python_background_executable(self) -> str:
        """
        On Windows, use pythonw.exe to avoid ANY console window.
        On other platforms, just use sys.executable.
        """
        if sys.platform != "win32":
            return sys.executable

        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        return str(pyw) if pyw.exists() else str(exe)

    # ----------------------------
    # Background process start
    # ----------------------------

    def _start_background_process(
        self,
        command: list[str],
        pid_file: Path,
        name: str,
        log_file: Path,
    ) -> Optional[int]:
        """
        Start a background process (cross-platform).

        - Redirect stdout/stderr to UTF-8 log file.
        - stdin=DEVNULL to avoid inheriting console handles.
        - cwd fixed to FAILCORE_ROOT.
        - Windows: pythonw.exe + CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP
        - Unix: start_new_session=True (new session/process group)
        """
        # Ensure log banner exists before launching
        _append_log_banner(log_file, name, extra=f"cwd={FAILCORE_ROOT}")

        # Create timestamped log writer
        try:
            log_writer = TimestampedLogWriter(log_file)
        except Exception as e:
            print(f"Error: Failed to open log file {log_file}: {e}", file=sys.stderr)
            return None

        env = _default_child_env()

        try:
            if sys.platform == "win32":
                import subprocess as sp

                # Key: hide console + new process group for better stop/kill-tree semantics
                creationflags = sp.CREATE_NO_WINDOW | get_process_group_creation_flags()

                proc = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    cwd=str(FAILCORE_ROOT),
                    env=env,
                    close_fds=False,
                )
            else:
                proc = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    cwd=str(FAILCORE_ROOT),
                    env=env,
                    close_fds=True,
                )

            pid = proc.pid

            # Start timestamped log writer
            log_writer.start(proc.stdout)

            # Record PID
            try:
                _write_pid(pid_file, pid)
            except Exception as e:
                print(f"Warning: Failed to write PID file {pid_file}: {e}", file=sys.stderr)

            # Give it a moment to start
            time.sleep(0.5)

            if pid_exists(pid):
                # Process is running, log_writer will continue in background
                # Note: log_writer thread will stop automatically when process exits
                return pid

            # Exited immediately - stop log writer
            try:
                log_writer.stop()
            except Exception:
                pass
            _remove_file_silent(pid_file)
            _append_log_banner(log_file, name, extra=f"ERROR: {name} (PID {pid}) exited immediately")
            print(f"Error: {name} (PID {pid}) exited immediately. Check logs: {log_file}", file=sys.stderr)
            return None

        except Exception as e:
            try:
                log_writer.stop()
            except Exception:
                pass
            _append_log_banner(log_file, name, extra=f"ERROR: Failed to start {name}: {e}")
            print(f"Error: Failed to start {name}: {e}", file=sys.stderr)
            return None

    # ----------------------------
    # Start / Stop services
    # ----------------------------

    def start_proxy(self, listen: str = f"127.0.0.1:{DEFAULT_PROXY_PORT}") -> bool:
        if self.is_proxy_running():
            print("Proxy is already running", file=sys.stderr)
            return False

        python_exe = self._get_python_background_executable()

        command = [
            python_exe,
            "-m", "failcore.cli.main",
            "proxy",
            "--listen", listen,
        ]

        pid = self._start_background_process(
            command=command,
            pid_file=PROXY_PID_FILE,
            name="proxy",
            log_file=PROXY_LOG_FILE,
        )

        info = self._load_info()
        if pid:
            info.proxy.update({"pid": pid, "listen": listen, "started_at": _now_iso(), "log_file": str(PROXY_LOG_FILE.relative_to(FAILCORE_ROOT).as_posix())})
            self._save_info(info)
            print(f"✓ Proxy started (PID: {pid}, listen: {listen})")
            return True

        info.proxy.update({"pid": None, "listen": listen, "started_at": None, "log_file": str(PROXY_LOG_FILE.relative_to(FAILCORE_ROOT).as_posix())})
        self._save_info(info)
        print("✗ Failed to start proxy", file=sys.stderr)
        return False

    def start_ui(self, host: str = "127.0.0.1", port: int = DEFAULT_UI_PORT) -> bool:
        if self.is_ui_running():
            print("UI is already running", file=sys.stderr)
            return False

        python_exe = self._get_python_background_executable()

        command = [
            python_exe,
            "-m", "failcore.cli.main",
            "ui",
            "--host", host,
            "--port", str(port),
            "--no-browser",
        ]

        pid = self._start_background_process(
            command=command,
            pid_file=UI_PID_FILE,
            name="ui",
            log_file=UI_LOG_FILE,
        )

        info = self._load_info()
        if pid:
            info.ui.update({"pid": pid, "host": host, "port": port, "started_at": _now_iso(), "log_file": str(UI_LOG_FILE.relative_to(FAILCORE_ROOT).as_posix())})
            self._save_info(info)
            print(f"✓ UI started (PID: {pid}, http://{host}:{port})")
            return True

        info.ui.update({"pid": None, "host": host, "port": port, "started_at": None, "log_file": str(UI_LOG_FILE.relative_to(FAILCORE_ROOT).as_posix())})
        self._save_info(info)
        print("✗ Failed to start UI", file=sys.stderr)
        return False

    def _stop_by_pidfile(self, pid_file: Path, name: str) -> Tuple[str, Optional[int], Optional[str]]:
        """
        Stop a service by pidfile.
        Returns: (status, pid, error) where status in {"stopped", "not_running", "failed"}
        """
        pid = _read_pid(pid_file)
        if pid is None:
            return ("not_running", None, None)

        if not pid_exists(pid):
            _remove_file_silent(pid_file)
            return ("not_running", pid, "stale pid file")

        # Kill group/tree first
        success, err = kill_process_group(pgid=pid, timeout=5.0, signal_escalation=True)
        if not success:
            # Fallback: kill single PID
            s2, err2 = kill_process(pid, force=True, timeout=5.0, verify=False)
            if not s2:
                return ("failed", pid, err2 or err or "unknown error")

        time.sleep(0.2)
        if pid_exists(pid, timeout=1.0):
            return ("failed", pid, f"{name} still alive after stop attempts")

        _remove_file_silent(pid_file)
        return ("stopped", pid, None)

    def stop_proxy(self) -> Tuple[str, Optional[int], Optional[str]]:
        return self._stop_by_pidfile(PROXY_PID_FILE, "proxy")

    def stop_ui(self) -> Tuple[str, Optional[int], Optional[str]]:
        return self._stop_by_pidfile(UI_PID_FILE, "ui")


# ---------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------

def register_command(subparsers):
    """Register the 'service' command and its subcommands."""
    service_p = subparsers.add_parser(
        "service",
        help="Manage FailCore services (proxy + UI) as background processes",
    )
    service_sub = service_p.add_subparsers(dest="service_command", required=True)

    # service start
    start_p = service_sub.add_parser("start", help="Start proxy and UI services in background")
    start_p.add_argument(
        "--proxy-listen",
        default=f"127.0.0.1:{DEFAULT_PROXY_PORT}",
        help=f"Proxy listen address (default: 127.0.0.1:{DEFAULT_PROXY_PORT})",
    )
    start_p.add_argument(
        "--ui-host",
        default="127.0.0.1",
        help="UI host (default: 127.0.0.1)",
    )
    start_p.add_argument(
        "--ui-port",
        type=int,
        default=DEFAULT_UI_PORT,
        help=f"UI port (default: {DEFAULT_UI_PORT})",
    )
    start_p.set_defaults(func=service_start)

    # service stop
    stop_p = service_sub.add_parser("stop", help="Stop proxy and UI services")
    stop_p.set_defaults(func=service_stop)

    # service status
    status_p = service_sub.add_parser("status", help="Show service status")
    status_p.set_defaults(func=service_status)

    return service_p


def service_start(args):
    manager = ServiceManager()

    print("Starting FailCore services...")
    print()

    proxy_ok = manager.start_proxy(args.proxy_listen)
    ui_ok = manager.start_ui(args.ui_host, args.ui_port)

    print()
    if proxy_ok and ui_ok:
        print("✓ All services started successfully")
        print()
    else:
        print("⚠ Some services failed to start (check logs below)", file=sys.stderr)
        print()

    print(f"  Proxy: http://{args.proxy_listen}")
    print(f"  UI:    http://{args.ui_host}:{args.ui_port}")
    # Convert to relative paths (from FAILCORE_ROOT) and use forward slashes
    log_dir_rel = f".failcore/{LOG_DIR.relative_to(FAILCORE_ROOT).as_posix()}"
    service_dir_rel = f".failcore/{SERVICE_DIR.relative_to(FAILCORE_ROOT).as_posix()}"
    info_file_rel = f".failcore/{SERVICE_INFO_FILE.relative_to(FAILCORE_ROOT).as_posix()}"
    print(f"  Logs:  {log_dir_rel}/*.log")
    print(f"  PIDs:  {service_dir_rel}/*.pid")
    print(f"  Info:  {info_file_rel}")
    return 0 if (proxy_ok and ui_ok) else 1


def service_stop(args):
    manager = ServiceManager()

    print("Stopping FailCore services...")
    print()

    proxy_status, proxy_pid, proxy_err = manager.stop_proxy()
    ui_status, ui_pid, ui_err = manager.stop_ui()

    def _line(name: str, status: str, pid: Optional[int], err: Optional[str]) -> str:
        if status == "stopped":
            return f"✓ {name}: stopped (PID: {pid})"
        if status == "not_running":
            return f"• {name}: not running"
        return f"✗ {name}: failed to stop (PID: {pid}) - {err or 'unknown error'}"

    print(_line("Proxy", proxy_status, proxy_pid, proxy_err))
    print(_line("UI", ui_status, ui_pid, ui_err))
    print()

    if proxy_status == "failed" or ui_status == "failed":
        return 1
    return 0


def service_status(args):
    manager = ServiceManager()
    info = manager._load_info()

    print("FailCore Service Status")
    print("=" * 50)
    print()

    proxy_running = manager.is_proxy_running()
    proxy_pid = manager.get_proxy_pid()
    proxy_listen = info.proxy.get("listen")
    if proxy_running:
        listen = proxy_listen or "unknown"
        print(f"✓ Proxy:  Running (PID: {proxy_pid}, listen: {listen})")
    else:
        print("✗ Proxy:  Not running")

    ui_running = manager.is_ui_running()
    ui_pid = manager.get_ui_pid()
    ui_host = info.ui.get("host")
    ui_port = info.ui.get("port")
    if ui_running:
        host = ui_host or "127.0.0.1"
        port = ui_port or DEFAULT_UI_PORT
        print(f"✓ UI:     Running (PID: {ui_pid}, url: http://{host}:{port})")
    else:
        print("✗ UI:     Not running")

    print()
    # Convert to relative paths (from FAILCORE_ROOT) and use forward slashes
    service_dir_rel = SERVICE_DIR.relative_to(FAILCORE_ROOT).as_posix()
    log_dir_rel = LOG_DIR.relative_to(FAILCORE_ROOT).as_posix()
    info_file_rel = SERVICE_INFO_FILE.relative_to(FAILCORE_ROOT).as_posix()
    # Add .failcore prefix
    service_dir_rel = f".failcore/{service_dir_rel}"
    log_dir_rel = f".failcore/{log_dir_rel}"
    info_file_rel = f".failcore/{info_file_rel}"
    print(f"Service directory: {service_dir_rel}")
    print(f"Log directory:     {log_dir_rel}")
    print(f"Log files:         {log_dir_rel}/*.log")
    print(f"PID files:         {service_dir_rel}/*.pid")
    print(f"Info file:         {info_file_rel}")
    return 0


__all__ = ["register_command"]
