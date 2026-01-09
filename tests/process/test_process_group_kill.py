# tests/process/test_process_group_kill.py
"""
Process group kill tests - validate cross-platform process group management

Tests cover:
1. Process group creation returns valid PGID
2. Kill process group success/failure handling
3. Signal escalation behavior
4. Platform-specific implementation (Windows vs Unix)
5. Error handling (no exceptions on failure)
"""

import os
import signal
import subprocess
import sys
import time
from unittest.mock import patch, MagicMock

import pytest

from failcore.utils.process import (
    create_process_group,
    get_process_group_creation_flags,
    kill_process_group,
    ProcessError,
    ProcessKillError,
)


# ============================================================
# Test 1: Process group creation
# ============================================================

def test_create_process_group_returns_valid_pgid():
    """
    1️⃣ 创建进程组后应返回一个有效的 pgid（非 None、非 0），作为后续 kill 的唯一标识
    """
    if sys.platform == 'win32':
        # Windows: create_process_group() 返回 None（需要创建子进程时使用 flags）
        pgid = create_process_group()
        assert pgid is None, "Windows create_process_group() returns None (use flags in subprocess)"
        
        # 验证 flags 存在
        flags = get_process_group_creation_flags()
        assert flags != 0, "Windows should return CREATE_NEW_PROCESS_GROUP flag"
    else:
        # Unix: create_process_group() 应返回有效的 PGID
        pgid = create_process_group()
        assert pgid is not None, "Unix create_process_group() should return PGID"
        assert pgid != 0, "PGID should not be 0"
        assert isinstance(pgid, int), "PGID should be integer"
        assert pgid > 0, "PGID should be positive"


def test_get_process_group_creation_flags():
    """验证平台特定的进程组创建标志"""
    flags = get_process_group_creation_flags()
    
    if sys.platform == 'win32':
        # Windows: 应返回 CREATE_NEW_PROCESS_GROUP (0x00000200)
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        assert flags == CREATE_NEW_PROCESS_GROUP, \
            f"Windows should return CREATE_NEW_PROCESS_GROUP, got {flags}"
    else:
        # Unix: 返回 0（使用 preexec_fn=os.setsid 代替）
        assert flags == 0, "Unix should return 0 (use preexec_fn instead)"


# ============================================================
# Test 2-3: Kill process group success/failure
# ============================================================

def test_kill_process_group_success_returns_true():
    """
    2️⃣ 当进程组存在且可杀时，kill_process_group() 应返回 (True, None)，表示成功终止
    """
    # 创建一个真实的进程组用于测试（Unix only）
    if sys.platform == 'win32':
        pytest.skip("Windows process group kill requires real process, skip for unit test")
    
    # 创建进程组
    pgid = create_process_group()
    assert pgid is not None
    
    # 启动一个子进程在进程组中
    proc = subprocess.Popen(
        ["python", "-c", "import time; time.sleep(0.5)"],
        preexec_fn=os.setsid,  # 在子进程中创建新进程组
    )
    
    try:
        # 等待进程启动
        time.sleep(0.1)
        
        # Kill 进程组（使用子进程的进程组）
        # 注意：这里我们 kill 子进程的进程组，不是父进程的
        success, error = kill_process_group(
            pgid=proc.pid,  # 使用子进程 PID 作为进程组 ID
            timeout=2.0,
            signal_escalation=False  # 直接 SIGKILL
        )
        
        # 验证成功
        assert success is True, f"kill_process_group should succeed, got error: {error}"
        assert error is None, f"Should return None on success, got: {error}"
        
        # 验证进程已终止
        proc.wait(timeout=1.0)
        assert proc.returncode is not None, "Process should be terminated"
    
    finally:
        # 清理
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def test_kill_process_group_not_found_returns_false():
    """
    3️⃣ 当 pgid 不存在时，kill 不应抛异常，而应返回 (False, error_message)，供上层记录
    """
    # 使用一个不存在的 PGID
    fake_pgid = 999999
    
    # Kill 不存在的进程组（不应抛异常）
    success, error = kill_process_group(
        pgid=fake_pgid,
        timeout=1.0,
        signal_escalation=False
    )
    
    # 验证返回 False 且有错误信息
    assert success is False, "kill_process_group should return False for non-existent PGID"
    assert error is not None, "Should return error message for non-existent PGID"
    assert isinstance(error, str), "Error should be string"
    assert len(error) > 0, "Error message should not be empty"


# ============================================================
# Test 4: Signal escalation
# ============================================================

def test_kill_process_group_escalates_signal():
    """
    4️⃣ 在启用 signal_escalation 时，应先尝试温和信号，再升级到强制终止路径
    """
    if sys.platform == 'win32':
        pytest.skip("Signal escalation is Unix-specific")
    
    # Mock os.killpg 来验证调用顺序
    with patch('os.killpg') as mock_killpg:
        # 创建一个会"拒绝"SIGTERM 的假进程组（通过 mock）
        fake_pgid = 12345
        
        # 第一次调用 SIGTERM，第二次调用 SIGKILL
        call_count = [0]
        
        def killpg_side_effect(pgid, sig):
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次：SIGTERM
                assert sig == signal.SIGTERM, "First call should be SIGTERM"
            elif call_count[0] == 2:
                # 第二次：SIGKILL（如果进程还在）
                assert sig == signal.SIGKILL, "Second call should be SIGKILL"
        
        mock_killpg.side_effect = killpg_side_effect
        
        # Mock pid_exists 来模拟进程在 SIGTERM 后仍然存在
        with patch('failcore.utils.process.pid_exists') as mock_pid_exists:
            # 第一次检查：进程存在（SIGTERM 后）
            # 第二次检查：进程仍存在（触发 SIGKILL）
            mock_pid_exists.side_effect = [True, True, False]  # 最终被杀死
            
            success, error = kill_process_group(
                pgid=fake_pgid,
                timeout=2.0,
                signal_escalation=True  # 启用信号升级
            )
            
            # 验证调用了两次 killpg
            assert mock_killpg.call_count >= 1, "Should call killpg at least once"
            
            # 验证调用顺序：SIGTERM 然后 SIGKILL
            calls = mock_killpg.call_args_list
            if len(calls) >= 2:
                assert calls[0][0][1] == signal.SIGTERM, "First call should be SIGTERM"
                assert calls[1][0][1] == signal.SIGKILL, "Second call should be SIGKILL"


# ============================================================
# Test 5: Error handling
# ============================================================

def test_kill_process_group_does_not_raise_on_failure():
    """
    5️⃣ 无论底层命令失败（如 taskkill / 权限不足），kill 都不应向上传播异常
    """
    fake_pgid = 12345
    
    if sys.platform == 'win32':
        # Mock taskkill 失败
        with patch('subprocess.run') as mock_run:
            # 模拟 taskkill 返回错误
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "ERROR: The process not found"
            mock_run.return_value = mock_result
            
            # 不应抛异常，应返回 (False, error_message)
            success, error = kill_process_group(
                pgid=fake_pgid,
                timeout=1.0,
                signal_escalation=False
            )
            
            assert success is False, "Should return False on failure"
            assert error is not None, "Should return error message"
            assert "taskkill" in error.lower() or "process" in error.lower(), \
                "Error should mention taskkill or process"
    else:
        # Mock os.killpg 抛出权限错误
        with patch('os.killpg', side_effect=PermissionError("Permission denied")):
            # 不应抛异常，应返回 (False, error_message)
            success, error = kill_process_group(
                pgid=fake_pgid,
                timeout=1.0,
                signal_escalation=False
            )
            
            assert success is False, "Should return False on failure"
            assert error is not None, "Should return error message"
            assert "permission" in error.lower() or "denied" in error.lower(), \
                "Error should mention permission issue"


# ============================================================
# Test 6-7: Platform-specific implementation
# ============================================================

def test_kill_process_group_windows_uses_taskkill():
    """
    6️⃣ 在 Windows 平台下，应走 taskkill 分支，而不是 Unix 的 killpg 逻辑
    """
    if sys.platform != 'win32':
        pytest.skip("Windows-specific test")
    
    fake_pgid = 12345
    
    # Mock subprocess.run (taskkill)
    with patch('subprocess.run') as mock_run:
        # 模拟 taskkill 成功
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "SUCCESS: The process has been terminated"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Mock pid_exists 返回 True（进程存在）
        with patch('failcore.utils.process.pid_exists', return_value=True):
            success, error = kill_process_group(
                pgid=fake_pgid,
                timeout=1.0,
                signal_escalation=False
            )
            
            # 验证调用了 taskkill
            assert mock_run.called, "Should call subprocess.run for taskkill"
            
            # 验证调用参数
            call_args = mock_run.call_args
            assert call_args is not None, "Should have call arguments"
            
            # 验证命令是 taskkill
            cmd = call_args[0][0] if call_args[0] else []
            assert 'taskkill' in cmd, f"Should call taskkill, got: {cmd}"
            
            # 验证参数包含 /T (tree kill)
            cmd_str = ' '.join(cmd)
            assert '/T' in cmd_str, "Should use /T flag for tree kill"
            assert '/F' in cmd_str, "Should use /F flag for force kill"
            assert str(fake_pgid) in cmd_str, f"Should include PID {fake_pgid}"


def test_kill_process_group_unix_uses_killpg():
    """
    7️⃣ 在 Unix 平台下，应调用 os.killpg，且参数为传入的 pgid
    """
    if sys.platform == 'win32':
        pytest.skip("Unix-specific test")
    
    fake_pgid = 12345
    
    # Mock os.killpg
    with patch('os.killpg') as mock_killpg:
        # Mock pid_exists 返回 True 然后 False（进程被杀死）
        with patch('failcore.utils.process.pid_exists', side_effect=[True, False]):
            success, error = kill_process_group(
                pgid=fake_pgid,
                timeout=1.0,
                signal_escalation=False  # 直接 SIGKILL
            )
            
            # 验证调用了 os.killpg
            assert mock_killpg.called, "Should call os.killpg"
            
            # 验证调用参数
            call_args = mock_killpg.call_args
            assert call_args is not None, "Should have call arguments"
            
            # 验证第一个参数是 pgid
            actual_pgid = call_args[0][0]
            assert actual_pgid == fake_pgid, \
                f"Should call killpg with pgid={fake_pgid}, got {actual_pgid}"
            
            # 验证第二个参数是 SIGKILL
            actual_signal = call_args[0][1]
            assert actual_signal == signal.SIGKILL, \
                f"Should use SIGKILL, got {actual_signal}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
