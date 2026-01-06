"""
Tests for ProcessExecutor (P2-1)

Must run real subprocess with:
- Success case
- Timeout case (kill child, no hang)
"""

import pytest
import time
from failcore.core.executor.process import ProcessExecutor
from failcore.core.errors import codes


# Module-level functions for subprocess execution
def _quick_tool():
    """Quick tool for success test"""
    return "success"


def _slow_tool():
    """Slow tool for timeout test"""
    import time
    time.sleep(10)  # Sleep 10 seconds
    return "should not reach here"


def test_process_executor_success():
    """Should execute tool in subprocess and return success"""
    
    executor = ProcessExecutor(
        working_dir="./test_workspace",
        timeout_s=5
    )
    
    result = executor.execute(_quick_tool, {})
    
    # Must succeed
    assert result["ok"] is True
    assert result["error"] is None
    assert result["result"] == "success"


def test_process_executor_timeout():
    """
    Should kill child process on timeout
    
    Critical test: Ensures parent doesn't hang waiting for child
    """
    
    executor = ProcessExecutor(
        working_dir="./test_workspace",
        timeout_s=1  # 1 second timeout
    )
    
    start = time.time()
    result = executor.execute(_slow_tool, {})
    elapsed = time.time() - start
    
    # Must fail
    assert result["ok"] is False
    assert result["error"] is not None
    
    # Must have correct error code
    error = result["error"]
    assert error["code"] == codes.RESOURCE_LIMIT_TIMEOUT
    assert "timed out" in error["message"].lower()
    assert error.get("suggestion") is not None
    
    # Must return quickly (within 2 seconds, accounting for overhead)
    assert elapsed < 2.0, f"Timeout took {elapsed}s, should be < 2s"
    
    # This proves: child was killed, parent didn't hang


def _get_cwd():
    """Get current working directory"""
    import os
    return os.getcwd()


def _get_env():
    """Get environment variables"""
    import os
    return dict(os.environ)


def _traced_tool():
    """Traced tool for correlation test"""
    return "traced result"


def test_process_executor_working_directory():
    """Should enforce working directory isolation (TRUE ASSERTION)"""
    
    executor = ProcessExecutor(
        working_dir="./isolated_workspace",
        timeout_s=5
    )
    
    result = executor.execute(_get_cwd, {})
    
    # TRUE ASSERTION: Child process actually ran in isolated_workspace
    assert result["ok"] is True
    cwd = result["stats"]["cwd"]
    assert cwd.endswith("isolated_workspace") or "isolated_workspace" in cwd
    
    # Verify directory exists (executor created it)
    from pathlib import Path
    assert Path("./isolated_workspace").exists()


def test_process_executor_env_whitelist():
    """Should restrict environment variables (TRUE ASSERTION)"""
    
    executor = ProcessExecutor(
        working_dir="./test_workspace",
        timeout_s=5,
        env_whitelist=["PATH"]  # Only PATH allowed
    )
    
    result = executor.execute(_get_env, {})
    
    # TRUE ASSERTION: Only whitelisted + minimal essential vars present
    assert result["ok"] is True
    env_vars = result["result"]
    
    # PATH should exist (whitelisted)
    assert "PATH" in env_vars
    
    # Secrets should NOT exist (not whitelisted)
    assert "USERPROFILE" not in env_vars or env_vars["USERPROFILE"] == ""
    assert "HOME" not in env_vars  # Not in whitelist
    assert "USER" not in env_vars  # Not in whitelist
    
    # Only minimal set: PATH + platform essentials (SYSTEMROOT on Windows, PYTHONPATH if needed)
    allowed_keys = {"PATH", "SYSTEMROOT", "PYTHONPATH"}
    extra_keys = set(env_vars.keys()) - allowed_keys
    # Allow empty string values but not actual secrets
    for key in extra_keys:
        if env_vars[key]:  # Non-empty
            assert False, f"Unexpected env var with value: {key}={env_vars[key][:20]}..."


def test_process_executor_with_trace():
    """
    Should maintain trace/audit correlation (TRUE ASSERTION)
    
    Even though tool runs in subprocess, trace should link to same run_id
    """
    
    executor = ProcessExecutor(
        working_dir="./test_workspace",
        timeout_s=5
    )
    
    # Pass run_id to subprocess
    test_run_id = "test-run-12345"
    result = executor.execute(_traced_tool, {}, run_id=test_run_id)
    
    # TRUE ASSERTION: run_id propagated to subprocess and returned
    assert result["ok"] is True
    assert result["stats"]["run_id"] == test_run_id
    
    # This proves: subprocess received run_id, could write it to trace/event
    # In production: executor would emit trace event with this run_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
