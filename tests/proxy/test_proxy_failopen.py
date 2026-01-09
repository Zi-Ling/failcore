"""
Fail-open tests - Errors in sinks/enrichers don't break proxy

Tests that proxy continues to work even when:
- TraceSink write fails
- Enricher raises exception
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from failcore.core.proxy import ProxyPipeline
from failcore.core.egress import EgressEngine, TraceSink, UsageEnricher
from failcore.core.egress.types import EgressEvent, EgressType

# Use anyio for async tests
pytestmark = pytest.mark.anyio


class FailingTraceSink(TraceSink):
    """TraceSink that always fails on write"""
    
    def write(self, event: EgressEvent) -> None:
        """Always raise exception"""
        raise RuntimeError("TraceSink write failed (simulated)")


class BadEnricher:
    """Enricher that always raises exception"""
    
    def enrich(self, event: EgressEvent) -> None:
        """Always raise exception"""
        raise ValueError("BadEnricher failed (simulated)")


class MockUpstreamClient:
    """Mock upstream"""
    
    async def forward_request(self, url, method, headers, body):
        return {
            "status": 200,
            "headers": {"content-type": "application/json"},
            "body": b'{"id": "test"}',
        }


class TestFailOpenTraceSink:
    """Test fail-open when TraceSink fails"""
    
    @pytest.fixture
    def temp_trace_dir(self):
        """Temporary directory"""
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
    def failing_engine(self, temp_trace_dir):
        """Engine with failing sink"""
        trace_path = temp_trace_dir / "failing_trace.jsonl"
        failing_sink = FailingTraceSink(
            trace_path,
            async_mode=False,
            run_id="test_run",
            kind="proxy",
        )
        enrichers = [UsageEnricher()]
        engine = EgressEngine(trace_sink=failing_sink, enrichers=enrichers)
        yield engine
        # Cleanup: close engine and file handles
        try:
            engine.flush()
            engine.close()
            # Explicitly close the trace_sink's writer file handle
            if hasattr(failing_sink, '_writer') and hasattr(failing_sink._writer, '_file'):
                try:
                    if not failing_sink._writer._file.closed:
                        failing_sink._writer._file.close()
                except Exception:
                    pass
        except Exception:
            pass
    
    async def test_trace_sink_failure_doesnt_break_request(self, failing_engine):
        """Test that TraceSink failure doesn't break request"""
        pipeline = ProxyPipeline(egress_engine=failing_engine, upstream_client=MockUpstreamClient())
        
        # Request should succeed despite sink failure
        response = await pipeline.process_request(
            provider="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            headers={},
            body=b'{}',
            run_id="test_run",
            step_id="test_step",
        )
        
        # Assert request succeeded
        assert response["status"] == 200
        
        # Pipeline should not raise exception
        # (Exception is caught in EgressEngine.emit)


class TestFailOpenEnricher:
    """Test fail-open when Enricher fails"""
    
    @pytest.fixture
    def temp_trace_dir(self):
        """Temporary directory"""
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
    def engine_with_bad_enricher(self, temp_trace_dir):
        """Engine with bad enricher"""
        trace_path = temp_trace_dir / "bad_enricher_trace.jsonl"
        trace_sink = TraceSink(
            trace_path,
            async_mode=False,
            run_id="test_run",
            kind="proxy",
        )
        enrichers = [BadEnricher(), UsageEnricher()]  # Bad first, then good
        engine = EgressEngine(trace_sink=trace_sink, enrichers=enrichers)
        yield engine
        # Cleanup: close engine and file handles
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
    
    async def test_enricher_failure_doesnt_break_request(self, engine_with_bad_enricher, temp_trace_dir):
        """Test that Enricher failure doesn't break request"""
        pipeline = ProxyPipeline(
            egress_engine=engine_with_bad_enricher,
            upstream_client=MockUpstreamClient()
        )
        
        # Request should succeed despite enricher failure
        response = await pipeline.process_request(
            provider="openai",
            endpoint="/v1/chat/completions",
            method="POST",
            headers={},
            body=b'{}',
            run_id="test_run",
            step_id="test_step",
        )
        
        # Assert request succeeded
        assert response["status"] == 200
        
        # Trace should still be written (other enrichers and sink continue)
        trace_path = temp_trace_dir / "bad_enricher_trace.jsonl"
        assert trace_path.exists()
        
        # Evidence should not contain bad enricher content
        # (BadEnricher failed, so its modifications shouldn't appear)
        with open(trace_path, 'r') as f:
            content = f.read()
            # Should not contain bad enricher marker (if it had one)
            # For now, just verify trace was written
            assert len(content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
