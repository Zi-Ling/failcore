"""
Tests for Proxy Pipeline - Core request processing

Tests the unified request pipeline that routes through EgressEngine.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from failcore.core.proxy import ProxyConfig, ProxyPipeline
from failcore.core.egress import EgressEngine, TraceSink, UsageEnricher, DLPEnricher, TaintEnricher
from failcore.core.egress.types import EgressType, PolicyDecision
from tests.proxy.assertions import read_jsonl, assert_has_event, assert_event_fields

# Use anyio for async tests (already installed)
pytestmark = pytest.mark.anyio


class MockUpstreamClient:
    """Mock upstream client for testing"""
    
    async def forward_request(self, url, method, headers, body):
        """Mock forward request"""
        return {
            "status": 200,
            "headers": {"content-type": "application/json"},
            "body": b'{"id": "chatcmpl-123", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}',
        }


class TestProxyPipeline:
    """Test ProxyPipeline request processing"""
    
    @pytest.fixture
    def temp_trace_dir(self):
        """Create temporary trace directory"""
        # Use mkdtemp and manual cleanup to ensure files are closed first
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        # Cleanup happens after all fixtures are torn down
        try:
            shutil.rmtree(tmpdir)
        except PermissionError:
            # On Windows, files may still be locked - this is acceptable for tests
            pass
    
    @pytest.fixture
    def egress_engine(self, temp_trace_dir):
        """Create egress engine with trace sink"""
        trace_path = temp_trace_dir / "test_trace.jsonl"
        # Use small buffer_size=1 to ensure immediate flush on write
        trace_sink = TraceSink(
            trace_path,
            async_mode=False,
            buffer_size=1,
            flush_interval_s=0.0,
            run_id="test_run",
            kind="proxy",
        )
        enrichers = [UsageEnricher(), DLPEnricher(), TaintEnricher()]
        engine = EgressEngine(trace_sink=trace_sink, enrichers=enrichers)
        yield engine
        # Cleanup: flush and close engine (ensures file handle is closed)
        try:
            engine.flush()
            engine.close()
            # Explicitly close the trace_sink's writer file handle
            if hasattr(trace_sink, '_writer') and hasattr(trace_sink._writer, '_file'):
                try:
                    if not trace_sink._writer._file.closed:
                        trace_sink._writer._file.close()
                except Exception:
                    pass
        except Exception:
            pass
    
    @pytest.fixture
    def pipeline(self, egress_engine):
        """Create pipeline with mock upstream"""
        upstream = MockUpstreamClient()
        return ProxyPipeline(egress_engine=egress_engine, upstream_client=upstream)
    
    async def test_process_request_success(self, pipeline):
        """Test successful request processing"""
        response = await pipeline.process_request(
            provider="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            headers={"Authorization": "Bearer sk-test"},
            body=b'{"model": "gpt-4", "messages": []}',
            run_id="test_run",
            step_id="test_step",
        )
        
        assert response["status"] == 200
        assert "body" in response
    
    async def test_process_request_emits_egress_events(self, pipeline, egress_engine, temp_trace_dir):
        """Test that pipeline emits egress events"""
        await pipeline.process_request(
            provider="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            headers={},
            body=b'{}',
            run_id="test_run",
            step_id="test_step",
        )
        
        # Flush trace sink (sync mode, so flush is sufficient)
        egress_engine.flush()
        
        # Verify trace file was created
        trace_path = temp_trace_dir / "test_trace.jsonl"
        assert trace_path.exists(), f"Trace file not created at {trace_path}"
        
        # Read trace events using assertions (before close, so we can read it)
        events = read_jsonl(trace_path)
        
        # Close after reading (on Windows, file handle must be closed before temp dir cleanup)
        egress_engine.close()
        
        assert len(events) > 0, f"No events found in trace. File exists: {trace_path.exists()}, Size: {trace_path.stat().st_size if trace_path.exists() else 0}"
        
        # Assert NETWORK egress event exists
        network_event = assert_has_event(events, egress="NETWORK")
        assert_event_fields(
            network_event,
            required=["egress", "action", "target", "run_id", "step_id"],
            exact={"egress": "NETWORK", "run_id": "test_run", "step_id": "test_step"},
        )
    
    async def test_process_request_error_handling(self, pipeline):
        """Test error handling in pipeline"""
        # Create pipeline with failing upstream
        class FailingUpstream:
            async def forward_request(self, url, method, headers, body):
                raise Exception("Upstream error")
        
        failing_pipeline = ProxyPipeline(
            egress_engine=pipeline.egress_engine,
            upstream_client=FailingUpstream()
        )
        
        with pytest.raises(Exception, match="Upstream error"):
            await failing_pipeline.process_request(
                provider="openai",
                endpoint="/v1/chat/completions",
                method="POST",
                headers={},
                body=b'{}',
                run_id="test_run",
                step_id="test_step",
            )
    
    def test_create_pre_event(self, pipeline):
        """Test pre-call event creation"""
        event = pipeline._create_pre_event(
            provider="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            headers={"Authorization": "Bearer sk-test"},
            body=b'{}',
            run_id="test_run",
            step_id="test_step",
        )
        
        assert event.egress == EgressType.NETWORK
        assert event.action == "proxy.post"
        assert "openai" in event.target
        assert event.run_id == "test_run"
        assert event.step_id == "test_step"
        assert event.decision == PolicyDecision.ALLOW
        assert "provider" in event.evidence
        assert event.evidence["provider"] == "openai"


class TestProxyConfig:
    """Test ProxyConfig"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = ProxyConfig()
        
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.enable_streaming is True
        assert config.streaming_strict_mode is False
        assert config.enable_dlp is True
        assert config.dlp_strict_mode is False
        assert config.drop_on_full is True
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = ProxyConfig(
            host="0.0.0.0",
            port=9000,
            streaming_strict_mode=True,
            dlp_strict_mode=True,
            run_id="custom_run",
        )
        
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.streaming_strict_mode is True
        assert config.dlp_strict_mode is True
        assert config.run_id == "custom_run"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
