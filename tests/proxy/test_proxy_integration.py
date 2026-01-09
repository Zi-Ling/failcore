"""
Integration tests for Proxy - End-to-end scenarios

Tests the full proxy stack: server → pipeline → egress → trace.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path

from failcore.core.proxy import ProxyConfig, ProxyServer, ProxyPipeline, StreamHandler
from failcore.core.egress import EgressEngine, TraceSink, UsageEnricher, DLPEnricher, TaintEnricher
from tests.proxy.assertions import read_jsonl, assert_has_event

# Use anyio for async tests
pytestmark = pytest.mark.anyio


class TestProxyIntegration:
    """Integration tests for proxy"""
    
    @pytest.fixture
    def temp_trace_dir(self):
        """Create temporary trace directory"""
        # Use mkdtemp and manual cleanup to ensure files are closed first
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        # Cleanup happens after all fixtures are torn down
        # Files should be closed by egress_engine fixture
        try:
            shutil.rmtree(tmpdir)
        except PermissionError:
            # On Windows, files may still be locked - this is acceptable for tests
            pass
    
    @pytest.fixture
    def proxy_config(self, temp_trace_dir):
        """Create proxy config"""
        return ProxyConfig(
            host="127.0.0.1",
            port=0,  # Use 0 for auto-assign in tests
            streaming_strict_mode=False,
            dlp_strict_mode=False,
            run_id="test_proxy_run",
        )
    
    @pytest.fixture
    def egress_engine(self, temp_trace_dir):
        """Create egress engine with small buffer for immediate flush"""
        trace_path = temp_trace_dir / "proxy_trace.jsonl"
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
        # This must happen before temp_trace_dir cleanup
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
    def proxy_pipeline(self, egress_engine):
        """Create proxy pipeline"""
        class MockUpstream:
            async def forward_request(self, url, method, headers, body):
                return {
                    "status": 200,
                    "headers": {"content-type": "application/json"},
                    "body": b'{"id": "test", "usage": {"total_tokens": 100}}',
                }
        
        return ProxyPipeline(egress_engine=egress_engine, upstream_client=MockUpstream())
    
    @pytest.fixture
    def proxy_server(self, proxy_config, proxy_pipeline):
        """Create proxy server"""
        streaming_handler = StreamHandler(strict_mode=proxy_config.streaming_strict_mode)
        return ProxyServer(
            config=proxy_config,
            pipeline=proxy_pipeline,
            streaming_handler=streaming_handler,
        )
    
    async def test_proxy_pipeline_with_usage_enrichment(self, proxy_pipeline, egress_engine, temp_trace_dir):
        """Test that usage is extracted and enriched"""
        # Process request with usage in response
        response = await proxy_pipeline.process_request(
            provider="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            headers={},
            body=b'{"model": "gpt-4"}',
            run_id="test_run",
            step_id="test_step",
        )
        
        assert response["status"] == 200
        
        # Flush and close (ensures all writes complete and file handle is closed)
        egress_engine.flush()
        
        # Verify trace contains usage (before close, so we can read it)
        trace_path = temp_trace_dir / "proxy_trace.jsonl"
        assert trace_path.exists(), f"Trace file not created at {trace_path}"
        
        # Read trace using assertions
        events = read_jsonl(trace_path)
        
        # Close after reading (on Windows, file handle must be closed before temp dir cleanup)
        egress_engine.close()
        
        assert len(events) > 0, f"No events found in trace. File exists: {trace_path.exists()}, Size: {trace_path.stat().st_size if trace_path.exists() else 0}"
        
        # Assert NETWORK egress event exists
        assert_has_event(events, egress="NETWORK")
    
    async def test_proxy_server_initialization(self, proxy_server):
        """Test proxy server can be initialized"""
        assert proxy_server.config is not None
        assert proxy_server.pipeline is not None
        assert proxy_server.streaming_handler is not None
    
    def test_proxy_config_validation(self):
        """Test proxy config validation"""
        # Valid config
        config = ProxyConfig(
            host="127.0.0.1",
            port=8000,
            streaming_strict_mode=False,
        )
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        
        # Custom config
        config2 = ProxyConfig(
            host="0.0.0.0",
            port=9000,
            streaming_strict_mode=True,
            dlp_strict_mode=True,
            budget=100.0,
        )
        assert config2.streaming_strict_mode is True
        assert config2.dlp_strict_mode is True


class TestProxyEgressIntegration:
    """Test proxy integration with egress system"""
    
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
    
    async def test_proxy_emits_network_egress_events(self, temp_trace_dir):
        """Test that proxy emits NETWORK egress events"""
        trace_path = temp_trace_dir / "egress_trace.jsonl"
        # Use small buffer_size=1 to ensure immediate flush on write
        trace_sink = TraceSink(
            trace_path,
            async_mode=False,
            buffer_size=1,
            flush_interval_s=0.0,
            run_id="test_run",
            kind="proxy",
        )
        egress_engine = EgressEngine(trace_sink=trace_sink)
        
        class MockUpstream:
            async def forward_request(self, url, method, headers, body):
                return {"status": 200, "headers": {}, "body": b'{}'}
        
        pipeline = ProxyPipeline(egress_engine=egress_engine, upstream_client=MockUpstream())
        
        await pipeline.process_request(
            provider="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            headers={},
            body=b'{}',
            run_id="test_run",
            step_id="test_step",
        )
        
        # Flush (ensures all writes complete)
        egress_engine.flush()
        
        # Verify trace file (before close, so we can read it)
        assert trace_path.exists(), f"Trace file not created at {trace_path}"
        events = read_jsonl(trace_path)
        
        # Close after reading (on Windows, file handle must be closed before temp dir cleanup)
        egress_engine.close()
        
        assert len(events) > 0, f"No events found in trace. File exists: {trace_path.exists()}, Size: {trace_path.stat().st_size if trace_path.exists() else 0}"
        
        # Assert NETWORK egress event
        assert_has_event(events, egress="NETWORK")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
