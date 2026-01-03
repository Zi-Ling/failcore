"""
Tests for Policy Packs (P1-2)

Each pack must have at least 2 tests: allow + deny
Must assert error_code, suggestion, audit_fields
"""

import pytest
from failcore import run, guard
from failcore.core.errors import FailCoreError, codes
from failcore.core.presets.packs.filesystem_safe import FilesystemSafePolicy
from failcore.core.presets.packs.http_safe import HttpSafePolicy


class TestFilesystemSafePack:
    """Test filesystem-safe pack executable contract"""
    
    def test_allow_safe_path(self):
        """Should allow paths within sandbox"""
        policy = FilesystemSafePolicy(sandbox="./test_sandbox")
        
        result = policy.allow(
            tool="write_file",
            args={"path": "data/safe.txt"},
            context={}
        )
        
        assert result.allowed is True
    
    def test_deny_path_traversal(self):
        """Should deny path traversal with correct error_code and suggestion"""
        policy = FilesystemSafePolicy(sandbox="./test_sandbox")
        
        result = policy.allow(
            tool="write_file",
            args={"path": "../etc/passwd"},
            context={}
        )
        
        # Assertions required by P1-2
        assert result.allowed is False
        assert result.error_code == codes.PATH_TRAVERSAL
        assert result.suggestion is not None
        assert "without '..'" in result.suggestion or "relative paths" in result.suggestion.lower()
        assert result.remediation is not None
        assert "vars" in result.remediation
    
    def test_deny_absolute_path(self):
        """Should deny absolute paths"""
        policy = FilesystemSafePolicy(sandbox="./test_sandbox")
        
        result = policy.allow(
            tool="write_file",
            args={"path": "/tmp/evil.txt"},
            context={}
        )
        
        assert result.allowed is False
        assert result.error_code == codes.SANDBOX_VIOLATION
        assert result.suggestion is not None
        assert "relative path" in result.suggestion.lower()
    
    def test_integration_with_run(self):
        """Test pack integration with run() context"""
        
        def write_file(path: str, content: str) -> str:
            import os
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            return f"Wrote {len(content)} bytes"
        
        # Create custom policy instance
        fs_policy = FilesystemSafePolicy(sandbox="./test_sandbox")
        
        with run(policy=fs_policy, sandbox="./test_sandbox", trace=None) as ctx:
            safe_write = guard(write_file, risk="high", effect="fs")
            
            # Should succeed for safe path
            result = safe_write(path="data/ok.txt", content="test")
            assert "bytes" in result
            
            # Should fail for path traversal
            with pytest.raises(FailCoreError) as exc_info:
                safe_write(path="../evil.txt", content="bad")
            
            error = exc_info.value
            assert error.error_code == codes.PATH_TRAVERSAL
            assert error.suggestion is not None


class TestHttpSafePack:
    """Test http-safe pack executable contract"""
    
    def test_allow_public_url(self):
        """Should allow public internet URLs"""
        policy = HttpSafePolicy()
        
        result = policy.allow(
            tool="fetch_url",
            args={"url": "https://api.example.com/data"},
            context={}
        )
        
        assert result.allowed is True
    
    def test_deny_ssrf_localhost(self):
        """Should deny localhost (SSRF) with correct error_code"""
        policy = HttpSafePolicy()
        
        result = policy.allow(
            tool="fetch_url",
            args={"url": "http://localhost:8080/admin"},
            context={}
        )
        
        # Assertions required by P1-2
        assert result.allowed is False
        assert result.error_code == codes.SSRF_BLOCKED
        assert result.suggestion is not None
        assert "private" in result.suggestion.lower() or "public" in result.suggestion.lower()
        assert result.remediation is not None
    
    def test_deny_ssrf_private_ip(self):
        """Should deny private IP ranges"""
        policy = HttpSafePolicy()
        
        test_cases = [
            "http://127.0.0.1/admin",
            "http://10.0.0.1/internal",
            "http://192.168.1.1/router",
            "http://169.254.169.254/metadata",  # AWS metadata
        ]
        
        for url in test_cases:
            result = policy.allow(
                tool="fetch_url",
                args={"url": url},
                context={}
            )
            
            assert result.allowed is False, f"Should block {url}"
            assert result.error_code == codes.SSRF_BLOCKED
            assert result.suggestion is not None


class TestMcpRemotePack:
    """Test mcp-remote pack error contract"""
    
    def test_remote_error_codes(self):
        """Verify REMOTE_* error codes are defined"""
        from failcore.core.errors import codes
        
        # All REMOTE_* codes must exist
        assert hasattr(codes, 'REMOTE_TIMEOUT')
        assert hasattr(codes, 'REMOTE_UNREACHABLE')
        assert hasattr(codes, 'REMOTE_PROTOCOL_MISMATCH')
        assert hasattr(codes, 'REMOTE_TOOL_NOT_FOUND')
        assert hasattr(codes, 'REMOTE_INVALID_PARAMS')
        assert hasattr(codes, 'REMOTE_SERVER_ERROR')
        assert hasattr(codes, 'RETRY_EXHAUSTED')
    
    def test_retry_policy_integration(self):
        """Verify mcp-remote pack has retry policy"""
        from failcore.core.retry.policy import RetryPolicy
        
        policy = RetryPolicy()
        
        # Should retry transient errors
        assert policy.should_retry(codes.REMOTE_TIMEOUT, retryable=True)
        assert policy.should_retry(codes.REMOTE_UNREACHABLE, retryable=True)
        assert policy.should_retry(codes.REMOTE_SERVER_ERROR, retryable=True)
        
        # Should NOT retry validation errors
        assert not policy.should_retry(codes.REMOTE_INVALID_PARAMS, retryable=True)
        assert not policy.should_retry(codes.REMOTE_TOOL_NOT_FOUND, retryable=True)
        assert not policy.should_retry(codes.REMOTE_PROTOCOL_MISMATCH, retryable=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
