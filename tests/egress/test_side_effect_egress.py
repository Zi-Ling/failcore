# tests/egress/test_side_effect_egress.py
"""
Egress-level integration tests for FailCore side_effect enforcement.

Definition of Done (per egress class):
- FS / EXEC / NETWORK / PROCESS:
  * allow case succeeds AND produces an observable side effect
  * block case is enforced BEFORE the side effect happens (observable negative evidence)
  * trace has at least *some* decision signal (best-effort; avoid coupling to exact event names)

Non-goals:
- Not testing custom policies in this test file.
- Not relying on external network (no httpbin).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
import httpx

# ============================================================
# 0) >>> ALIGN THESE IMPORTS/CONSTRUCTORS TO YOUR REAL CODE <<<
# ============================================================
#
# If your canonical imports differ, only adjust this section.

from failcore.core.types.step import Step, RunContext, StepStatus
from failcore.core.executor import Executor, ExecutorConfig
from failcore.core.tools import (
    ToolRegistry,
    ToolSpec,
    ToolMetadata,
    SideEffect,
    RiskLevel,
    DefaultAction,
)
from failcore.core.guards.effects.boundary import SideEffectBoundary
from failcore.core.guards.effects.side_effects import SideEffectCategory, SideEffectType
from failcore.core.validate import ValidatorRegistry


# ============================================================
# 1) In-memory trace recorder (best-effort assertions)
# ============================================================

class InMemoryTraceRecorder:
    """
    Minimal recorder compatible with many implementations:
    - record(event) called with either dict or object having to_dict().
    """
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._seq = 0

    def record(self, event: Any):
        if isinstance(event, dict):
            self.events.append(event)
            return
        if hasattr(event, "to_dict"):
            self.events.append(event.to_dict())
            return
        self.events.append({"raw": str(event)})
    
    def next_seq(self) -> int:
        """Return next sequence number for trace events"""
        self._seq += 1
        return self._seq


def _trace_text(rec: InMemoryTraceRecorder) -> str:
    return "\n".join(str(e) for e in rec.events).lower()


def _extract_structured_fields(rec: InMemoryTraceRecorder) -> Dict[str, Any]:
    """
    Extract structured fields from trace events.
    Returns a dict with keys: decision, status, side_effect, error_code
    """
    result = {
        "decision": None,  # "allowed" or "blocked"
        "status": None,    # "ok" or "blocked"
        "side_effect": None,  # side effect type/category
        "error_code": None,   # error code from errors/code
    }
    
    for event in rec.events:
        # Navigate event structure
        event_data = event.get("event", {}) if isinstance(event, dict) else {}
        
        # Extract decision from policy/step_end events
        if "decision" in event_data:
            result["decision"] = event_data["decision"]
        elif "data" in event_data:
            data = event_data["data"]
            if isinstance(data, dict):
                # Check result.status
                result_data = data.get("result", {})
                if isinstance(result_data, dict):
                    if "status" in result_data:
                        result["status"] = result_data["status"]
                    # Check error.code
                    error_data = result_data.get("error", {})
                    if isinstance(error_data, dict):
                        if "code" in error_data:
                            result["error_code"] = error_data["code"]
                
                # Check policy decision
                policy_data = data.get("policy", {})
                if isinstance(policy_data, dict):
                    if "decision" in policy_data:
                        result["decision"] = policy_data["decision"]
        
        # Extract side_effect from side effect events
        if "side_effect" in event_data:
            result["side_effect"] = event_data["side_effect"]
        elif "data" in event_data:
            data = event_data["data"]
            if isinstance(data, dict) and "side_effect" in data:
                result["side_effect"] = data["side_effect"]
        
        # Extract error_code from error field
        if "error" in event_data:
            error = event_data["error"]
            if isinstance(error, dict) and "code" in error:
                result["error_code"] = error["code"]
    
    return result


def assert_trace_mentions(rec: InMemoryTraceRecorder, *, must_contain: List[str], 
                          expected_status: Optional[str] = None,
                          expected_error_code: Optional[str] = None,
                          expected_side_effect: Optional[str] = None):
    """
    Improved trace assertion: prioritize structured fields, fallback to text matching.
    
    Args:
        rec: Trace recorder
        must_contain: List of keywords that must appear in trace (fallback)
        expected_status: Expected status ("ok" or "blocked")
        expected_error_code: Expected error code
        expected_side_effect: Expected side effect type/category
    """
    # First, try structured field extraction
    fields = _extract_structured_fields(rec)
    
    # Check structured fields if provided
    if expected_status:
        actual_status = fields.get("status")
        if actual_status:
            assert actual_status == expected_status, \
                f"Expected status '{expected_status}', got '{actual_status}'"
    
    if expected_error_code:
        actual_error_code = fields.get("error_code")
        if actual_error_code:
            assert expected_error_code.lower() in actual_error_code.lower() or \
                   actual_error_code.lower() in expected_error_code.lower(), \
                f"Expected error_code containing '{expected_error_code}', got '{actual_error_code}'"
    
    if expected_side_effect:
        actual_side_effect = fields.get("side_effect")
        if actual_side_effect:
            side_effect_str = str(actual_side_effect).lower()
            expected_str = expected_side_effect.lower()
            assert expected_str in side_effect_str or side_effect_str in expected_str, \
                f"Expected side_effect containing '{expected_side_effect}', got '{actual_side_effect}'"
    
    # Fallback to text matching if structured fields are missing or as additional check
    hay = _trace_text(rec)
    missing = [s for s in must_contain if s.lower() not in hay]
    if missing:
        # Only fail if we couldn't verify via structured fields
        if not (expected_status and fields.get("status")) and \
           not (expected_error_code and fields.get("error_code")) and \
           not (expected_side_effect and fields.get("side_effect")):
            assert False, f"Trace missing expected signals: {missing}. Trace preview:\n{hay[:800]}"


# ============================================================
# 2) Local HTTP server for NETWORK tests (observable side-effect)
# ============================================================

class CountingHandler(BaseHTTPRequestHandler):
    request_count = 0

    def do_GET(self):
        CountingHandler.request_count += 1
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *_args):  # silence
        pass


def start_http_server(host: str = "127.0.0.1", port: int = 0) -> Tuple[HTTPServer, int]:
    srv = HTTPServer((host, port), CountingHandler)
    p = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)
    return srv, p


# ============================================================
# 3) Tools (minimal) with explicit side_effect metadata
# ============================================================

def tool_fs_write(path: str, content: str) -> Dict[str, Any]:
    """
    NOTE: resolve() is used so traversal attempts are unambiguous across cwd differences.
    """
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p), "n": len(content)}


def tool_exec(command: str, marker_path: str) -> Dict[str, Any]:
    """
    Observable: writes marker file BEFORE executing. If blocked, marker won't exist.
    """
    mp = Path(marker_path)
    mp.parent.mkdir(parents=True, exist_ok=True)

    mp.write_text(f"started:{command}\n", encoding="utf-8")
    p = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
    mp.write_text(
        f"started:{command}\ncompleted:{p.returncode}\nstdout:{p.stdout}\nstderr:{p.stderr}\n",
        encoding="utf-8",
    )
    return {"ok": p.returncode == 0, "rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def tool_http_get(url: str) -> Dict[str, Any]:
    r = httpx.get(url, timeout=2.0)
    return {"ok": True, "status": r.status_code, "n": len(r.content)}


def tool_spawn_sleep(seconds: int) -> Dict[str, Any]:
    """
    Spawn a process that sleeps. We return PID.
    NOTE: This tool itself is a PROCESS side effect (spawn).
    """
    p = subprocess.Popen(
        ["python", "-c", f"import time; time.sleep({int(seconds)})"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {"ok": True, "pid": p.pid}


def tool_kill(pid: int) -> Dict[str, Any]:
    """
    Kill a process by PID using robust cross-platform utilities.
    
    Uses failcore.utils.process.kill_process for proper error handling,
    timeout protection, and cross-platform compatibility.
    """
    from failcore.utils.process import kill_process
    
    # Use robust kill_process with timeout and verification
    success, error_msg = kill_process(
        pid,
        force=True,
        timeout=5.0,
        verify=True
    )
    
    return {
        "ok": success,
        "pid": pid,
        "error": error_msg if not success else None
    }


# ============================================================
# 4) Pytest fixtures for test harness
# ============================================================

@pytest.fixture
def temp_sandbox():
    """Create a temporary sandbox directory"""
    with tempfile.TemporaryDirectory() as td:
        sandbox = os.path.join(td, "sandbox")
        os.makedirs(sandbox, exist_ok=True)
        yield sandbox


@pytest.fixture
def executor_harness(temp_sandbox):
    """
    Fixture that provides executor, tools, recorder, validator.
    Returns a factory function that creates executor with boundary.
    """
    def _create_executor(boundary: SideEffectBoundary):
        tools = ToolRegistry(sandbox_root=temp_sandbox)
        rec = InMemoryTraceRecorder()

        validator = None
        try:
            validator = ValidatorRegistry()
        except Exception:
            validator = None

        ex = Executor(
            tools=tools,
            recorder=rec,
            validator=validator,
            side_effect_boundary=boundary,
            config=ExecutorConfig(enable_cost_tracking=False),
        )
        return ex, tools, rec, validator
    
    return _create_executor


@pytest.fixture
def run_context_factory(temp_sandbox):
    """Factory fixture for creating RunContext"""
    def _make_ctx(run_id: str) -> RunContext:
        return RunContext(
            run_id=run_id,
            created_at=time.time(),
            sandbox_root=temp_sandbox,
            cwd=temp_sandbox,
        )
    return _make_ctx


@pytest.fixture
def http_server():
    """
    Fixture for HTTP server with robust cleanup.
    
    Handles errors during shutdown gracefully with timeout and fallback strategies.
    """
    srv, port = start_http_server()
    CountingHandler.request_count = 0
    
    try:
        yield srv, port
    finally:
        # Robust cleanup with timeout and error handling
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Try graceful shutdown first
            srv.shutdown()
            logger.debug(f"HTTP server on port {port} shutdown successfully")
        except Exception as e:
            logger.warning(f"HTTP server shutdown failed: {e}")
        
        try:
            # Always try to close server socket
            srv.server_close()
            logger.debug(f"HTTP server on port {port} closed successfully")
        except Exception as e:
            logger.warning(f"HTTP server close failed: {e}")
        
        # Give server thread time to terminate
        try:
            time.sleep(0.1)
        except Exception:
            pass


@pytest.fixture
def process_cleanup():
    """
    Fixture to track and cleanup spawned processes with robust error handling.
    
    Uses failcore.utils.process.cleanup_processes for proper resource management.
    """
    from failcore.utils.process import cleanup_processes
    
    spawned_pids: List[int] = []
    spawned_procs: List[subprocess.Popen] = []
    
    def _register(proc: subprocess.Popen):
        """Register a process for cleanup"""
        spawned_procs.append(proc)
        spawned_pids.append(proc.pid)
        return proc
    
    yield _register
    
    # Robust cleanup using failcore.utils.process
    if spawned_pids:
        try:
            results = cleanup_processes(spawned_pids, timeout=10.0)
            
            # Log cleanup results
            failed = [pid for pid, success in results.items() if not success]
            if failed:
                import logging
                logging.warning(f"Failed to cleanup PIDs: {failed}")
        except Exception as e:
            import logging
            logging.error(f"Error during process cleanup: {e}", exc_info=True)
    
    # Additional fallback: try subprocess.Popen.kill() for any remaining
    for proc in spawned_procs:
        try:
            if proc.poll() is None:  # Still running
                proc.kill()
                proc.wait(timeout=1)
        except Exception:
            pass  # Best-effort, ignore errors


def attach_preconditions_if_any(*, tools: ToolRegistry, validator: Any, tool_name: str):
    """
    Best-effort: if registry supports get_preconditions() and validator supports register_precondition(),
    attach the builtin builtin assembled by auto_assemble=True.
    """
    if validator is None:
        return
    if not hasattr(tools, "get_preconditions"):
        return
    preconds = tools.get_preconditions(tool_name)  # type: ignore
    if not preconds:
        return
    if not hasattr(validator, "register_precondition"):
        return
    for p in preconds:
        validator.register_precondition(tool_name, p)


# ============================================================
# 5) FS tests (path traversal)
# ============================================================

def test_fs_allow_write_inside_sandbox(executor_harness, run_context_factory, temp_sandbox):
    boundary = SideEffectBoundary(
        allowed_categories={SideEffectCategory.FILESYSTEM},
        allowed_types={SideEffectType.FS_WRITE},
    )

    ex, tools, rec, validator = executor_harness(boundary)

    tools.register_tool(
        ToolSpec(
            name="fs_write",
            fn=tool_fs_write,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.FS,
                risk_level=RiskLevel.MEDIUM,
                default_action=DefaultAction.WARN,
            ),
        ),
        auto_assemble=True,
    )
    attach_preconditions_if_any(tools=tools, validator=validator, tool_name="fs_write")

    target = os.path.join(temp_sandbox, "ok.txt")
    step = Step(id="s1", tool="fs_write", params={"path": target, "content": "hello"})
    ctx = run_context_factory("fs-allow")

    r = ex.execute(step, ctx)

    assert r.status == StepStatus.OK
    assert Path(target).exists()
    assert Path(target).read_text(encoding="utf-8") == "hello"

    assert_trace_mentions(rec, must_contain=["fs", "filesystem"], expected_status="ok")


def test_fs_block_path_traversal_escape(executor_harness, run_context_factory, temp_sandbox):
    """
    IMPORTANT: Use an absolute target outside sandbox to avoid cwd-dependent behavior.
    """
    outside = os.path.join(os.path.dirname(temp_sandbox), "outside.txt")

    boundary = SideEffectBoundary(
        allowed_categories={SideEffectCategory.FILESYSTEM},
        allowed_types={SideEffectType.FS_WRITE},  # boundary allows, validator must block escape
    )

    ex, tools, rec, validator = executor_harness(boundary)

    tools.register_tool(
        ToolSpec(
            name="fs_write",
            fn=tool_fs_write,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.FS,
                risk_level=RiskLevel.MEDIUM,
                default_action=DefaultAction.WARN,
            ),
        ),
        auto_assemble=True,
    )
    attach_preconditions_if_any(tools=tools, validator=validator, tool_name="fs_write")

    # Attempt to write to an absolute file OUTSIDE sandbox.
    step = Step(id="s1", tool="fs_write", params={"path": outside, "content": "pwn"})
    ctx = run_context_factory("fs-block")

    r = ex.execute(step, ctx)

    assert r.status == StepStatus.BLOCKED
    assert not Path(outside).exists(), "must block before writing outside sandbox"

    assert_trace_mentions(rec, must_contain=["fs_write", "sandbox"], 
                         expected_status="blocked",
                         expected_error_code="SANDBOX_VIOLATION")


# ============================================================
# 6) EXEC tests (observable marker)
# ============================================================

def test_exec_allow_runs_and_writes_marker(executor_harness, run_context_factory, temp_sandbox):
    marker = os.path.join(temp_sandbox, "marker.txt")

    # Allow all EXEC types (subprocess, command, script)
    boundary = SideEffectBoundary(
        allowed_categories={SideEffectCategory.EXEC},
        # Don't specify allowed_types to allow all types in the category
    )

    ex, tools, rec, _validator = executor_harness(boundary)

    tools.register_tool(
        ToolSpec(
            name="exec",
            fn=tool_exec,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.EXEC,
                risk_level=RiskLevel.HIGH,
                default_action=DefaultAction.BLOCK,
            ),
        )
    )

    step = Step(id="s1", tool="exec", params={"command": "python --version", "marker_path": marker})
    ctx = run_context_factory("exec-allow")

    r = ex.execute(step, ctx)

    assert r.status == StepStatus.OK
    assert Path(marker).exists()
    txt = Path(marker).read_text(encoding="utf-8").lower()
    assert "started:" in txt and "completed:" in txt

    assert_trace_mentions(rec, must_contain=["exec"], expected_status="ok")


def test_exec_block_prevents_marker_creation(executor_harness, run_context_factory, temp_sandbox):
    marker = os.path.join(temp_sandbox, "marker.txt")

    boundary = SideEffectBoundary(
        allowed_categories=set(),
        blocked_categories={SideEffectCategory.EXEC},
    )

    ex, tools, rec, _validator = executor_harness(boundary)

    tools.register_tool(
        ToolSpec(
            name="exec",
            fn=tool_exec,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.EXEC,
                risk_level=RiskLevel.HIGH,
                default_action=DefaultAction.BLOCK,
            ),
        )
    )

    step = Step(id="s1", tool="exec", params={"command": "echo hello", "marker_path": marker})
    ctx = run_context_factory("exec-block")

    r = ex.execute(step, ctx)

    assert r.status == StepStatus.BLOCKED
    assert not Path(marker).exists(), "marker must not exist if blocked BEFORE tool runs"

    assert_trace_mentions(rec, must_contain=["exec"], 
                         expected_status="blocked",
                         expected_error_code="SIDE_EFFECT_BOUNDARY_CROSSED")


# ============================================================
# 7) NETWORK tests (local server hit count)
# ============================================================

def test_network_allow_hits_local_server(executor_harness, run_context_factory, http_server, temp_sandbox):
    """
    allow case: explicitly allowlist 127.0.0.1:port so builtin internal-ip-block (if present)
    is overridden by allowlist.
    """
    srv, port = http_server
    CountingHandler.request_count = 0

    boundary = SideEffectBoundary(
        allowed_categories={SideEffectCategory.NETWORK},
        allowed_types={SideEffectType.NET_EGRESS},
    )

    ex, tools, rec, validator = executor_harness(boundary)

    tools.register_tool(
        ToolSpec(
            name="http_get",
            fn=tool_http_get,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.NETWORK,
                risk_level=RiskLevel.HIGH,
                default_action=DefaultAction.BLOCK,
            ),
            # IMPORTANT: relies on your auto_assemble reading these keys.
            extras={
                "network_params": ["url"],
                "network_allowlist": [f"127.0.0.1:{port}"],
            },
        ),
        auto_assemble=True,
    )
    attach_preconditions_if_any(tools=tools, validator=validator, tool_name="http_get")

    before = CountingHandler.request_count
    step = Step(id="s1", tool="http_get", params={"url": f"http://127.0.0.1:{port}/x"})
    ctx = run_context_factory("net-allow")

    r = ex.execute(step, ctx)

    assert r.status == StepStatus.OK
    time.sleep(0.1)
    assert CountingHandler.request_count > before, "server must be hit to prove request actually happened"

    assert_trace_mentions(rec, must_contain=["network"], expected_status="ok")


def test_network_block_prevents_hitting_local_server(executor_harness, run_context_factory, http_server, temp_sandbox):
    """
    block case: do NOT provide allowlist; builtin internal-ip-block should deny 127.0.0.1.
    If your builtin builtin do not block loopback, this test will fail (and that's a real signal).
    """
    srv, port = http_server
    CountingHandler.request_count = 0

    boundary = SideEffectBoundary(
        allowed_categories={SideEffectCategory.NETWORK},
        allowed_types={SideEffectType.NET_EGRESS},
    )

    ex, tools, rec, validator = executor_harness(boundary)

    tools.register_tool(
        ToolSpec(
            name="http_get",
            fn=tool_http_get,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.NETWORK,
                risk_level=RiskLevel.HIGH,
                default_action=DefaultAction.BLOCK,
            ),
            extras={
                "network_params": ["url"],
                # No allowlist: expect internal/loopback block
            },
        ),
        auto_assemble=True,
    )
    attach_preconditions_if_any(tools=tools, validator=validator, tool_name="http_get")

    before = CountingHandler.request_count
    step = Step(id="s1", tool="http_get", params={"url": f"http://127.0.0.1:{port}/x"})
    ctx = run_context_factory("net-block")

    r = ex.execute(step, ctx)

    assert r.status == StepStatus.BLOCKED
    time.sleep(0.1)
    assert CountingHandler.request_count == before, "server must NOT be hit if blocked BEFORE tool runs"

    assert_trace_mentions(rec, must_contain=["http_get"], 
                         expected_status="blocked",
                         expected_error_code="SSRF_BLOCKED")


# ============================================================
# 8) PROCESS tests
# ============================================================

def _pid_exists(pid: int) -> bool:
    """
    Check if a process exists by PID using robust cross-platform utilities.
    
    Uses failcore.utils.process.pid_exists for proper error handling
    and cross-platform compatibility.
    """
    from failcore.utils.process import pid_exists
    
    return pid_exists(pid, timeout=2.0)


def test_process_allow_kill_only_if_spawned_by_session(executor_harness, run_context_factory, process_cleanup):
    """
    Acceptance depends on your implementation:
    - If you enforce ownership (spawn registry), this should pass.
    - If not, it may still pass (kill allowed) but that doesn't prove ownership.

    This test only verifies: spawn -> kill succeeds and process terminates (allow-path).
    """
    boundary = SideEffectBoundary(
        allowed_categories={SideEffectCategory.PROCESS},
        allowed_types={SideEffectType.PROCESS_SPAWN, SideEffectType.PROCESS_KILL},
    )

    ex, tools, rec, _validator = executor_harness(boundary)

    tools.register_tool(
        ToolSpec(
            name="spawn",
            fn=tool_spawn_sleep,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.PROCESS,
                risk_level=RiskLevel.HIGH,
                default_action=DefaultAction.BLOCK,
            ),
        )
    )
    tools.register_tool(
        ToolSpec(
            name="kill",
            fn=tool_kill,
            tool_metadata=ToolMetadata(
                side_effect=SideEffect.PROCESS,
                risk_level=RiskLevel.HIGH,
                default_action=DefaultAction.BLOCK,
            ),
        )
    )

    ctx = run_context_factory("proc-session")

    s1 = Step(id="s1", tool="spawn", params={"seconds": 10})
    r1 = ex.execute(s1, ctx)
    assert r1.status == StepStatus.OK
    out1 = r1.output.value if hasattr(r1.output, "value") else r1.output
    pid = int(out1["pid"])
    assert _pid_exists(pid)
    
    # Note: The process is spawned by the tool, we can't directly access the Popen object
    # The process_cleanup fixture will handle cleanup via PID if needed
    # For now, we rely on the kill tool to clean up, or manual cleanup at the end

    s2 = Step(id="s2", tool="kill", params={"pid": pid})
    r2 = ex.execute(s2, ctx)
    assert r2.status == StepStatus.OK
    # Wait longer for process to terminate (SIGKILL should be immediate, but give it time)
    time.sleep(0.5)
    assert not _pid_exists(pid), f"Process {pid} should be terminated after kill"

    assert_trace_mentions(rec, must_contain=["spawn", "kill"], expected_status="ok")
    
    # Cleanup: ensure process is terminated (in case kill didn't work)
    if _pid_exists(pid):
        from failcore.utils.process import kill_process
        try:
            kill_process(pid, force=True, timeout=2.0, verify=False)
        except Exception:
            pass  # Best-effort


def test_process_block_kill_foreign_pid_requires_ownership(executor_harness, run_context_factory, process_cleanup):
    """
    STRICT ownership test:
    - Start a process OUTSIDE the session spawn registry.
    - Attempt to kill it via tool.
    - Must be BLOCKED and process must remain alive.
    """
    foreign = subprocess.Popen(["python", "-c", "import time; time.sleep(10)"])
    foreign_pid = foreign.pid
    assert _pid_exists(foreign_pid)
    
    # Register for cleanup
    process_cleanup(foreign)

    try:
        boundary = SideEffectBoundary(
            allowed_categories={SideEffectCategory.PROCESS},
            allowed_types={SideEffectType.PROCESS_KILL},
        )

        ex, tools, rec, _validator = executor_harness(boundary)

        tools.register_tool(
            ToolSpec(
                name="kill",
                fn=tool_kill,
                tool_metadata=ToolMetadata(
                    side_effect=SideEffect.PROCESS,
                    risk_level=RiskLevel.HIGH,
                    default_action=DefaultAction.BLOCK,
                ),
            )
        )

        ctx = run_context_factory("proc-foreign")

        s = Step(id="s1", tool="kill", params={"pid": foreign_pid})
        r = ex.execute(s, ctx)

        assert r.status == StepStatus.BLOCKED, "must block killing foreign pid (ownership enforcement)"
        time.sleep(0.1)
        assert _pid_exists(foreign_pid), "foreign process must remain alive if blocked before execution"

        assert_trace_mentions(rec, must_contain=["process", "kill"], 
                            expected_status="blocked",
                            expected_error_code="PID_NOT_OWNED")
    finally:
        # Additional cleanup using robust utilities
        from failcore.utils.process import kill_process
        try:
            if _pid_exists(foreign_pid):
                kill_process(foreign_pid, force=True, timeout=2.0, verify=False)
        except Exception:
            pass  # Best-effort
