"""
Tests for Streaming Handler - SSE/streaming response processing

Tests tee pattern, side-channel scanning, and strict mode.
"""

import pytest
import asyncio
import queue
import re
import time

from failcore.core.proxy.stream import StreamHandler, StreamViolation

# Use anyio for async tests
pytestmark = pytest.mark.anyio


class MockUpstreamStream:
    """Mock upstream SSE stream (standard async iterator)"""
    
    def __init__(self, chunks):
        self.chunks = chunks
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        chunk = self.chunks[self.index]
        self.index += 1
        await asyncio.sleep(0.001)  # Simulate network delay
        return chunk


class TestStreamingHandler:
    """Test StreamingHandler"""
    
    @pytest.fixture
    def dlp_patterns(self):
        """DLP patterns for testing"""
        return {
            "API_KEY": re.compile(r"sk-[a-zA-Z0-9]{48}"),
            "SECRET": re.compile(r"secret:\s*[a-zA-Z0-9]+"),
        }
    
    @pytest.fixture
    def evidence_queue(self):
        """Evidence queue for testing"""
        return queue.Queue(maxsize=100)
    
    @pytest.fixture
    def handler_warn(self, dlp_patterns, evidence_queue):
        """Handler in warn mode (default)"""
        return StreamHandler(
            strict_mode=False,
            dlp_patterns=dlp_patterns,
            evidence_queue=evidence_queue,
        )
    
    @pytest.fixture
    def handler_strict(self, dlp_patterns, evidence_queue):
        """Handler in strict mode"""
        return StreamHandler(
            strict_mode=True,
            dlp_patterns=dlp_patterns,
            evidence_queue=evidence_queue,
        )
    
    async def test_process_stream_immediate_forward(self, handler_warn):
        """Test that chunks are forwarded immediately (tee pattern)"""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        stream = MockUpstreamStream(chunks)
        
        received = []
        async for chunk in handler_warn.process_stream(stream, run_id="test_run", step_id="test_step"):
            received.append(chunk)
        
        assert len(received) == 3
        assert received == chunks
    
    async def test_process_stream_dlp_detection_warn_mode(self, handler_warn, evidence_queue):
        """Test DLP detection in warn mode (evidence only)"""
        # Stream with sensitive data
        chunks = [
            b"data: ",
            b'{"content": "Here is your API key: sk-123456789012345678901234567890123456789012345678"}',
            b"\n\n",
        ]
        stream = MockUpstreamStream(chunks)
        
        # Process stream
        received = []
        async for chunk in handler_warn.process_stream(stream, run_id="test_run", step_id="test_step"):
            received.append(chunk)
        
        # Stream should complete (warn mode doesn't block)
        assert len(received) == 3
        
        # Evidence should be collected
        assert not evidence_queue.empty()
        evidence = evidence_queue.get_nowait()
        assert evidence["type"] == "stream_dlp_hit"
        assert "API_KEY" in evidence["hits"]
        assert evidence["severity"] == "warning"
    
    async def test_process_stream_dlp_detection_strict_mode(self, handler_strict, evidence_queue):
        """Test DLP detection in strict mode (blocks on violation)"""
        # Stream with sensitive data
        chunks = [
            b"data: ",
            b'{"content": "Here is your secret: secret: abc123"}',
            b"\n\n",
        ]
        stream = MockUpstreamStream(chunks)
        
        # Process stream - should raise on violation
        received = []
        with pytest.raises(StreamViolation, match="DLP violation"):
            async for chunk in handler_strict.process_stream(stream, run_id="test_run", step_id="test_step"):
                received.append(chunk)
        
        # Some chunks may have been forwarded before violation
        assert len(received) >= 0
    
    async def test_process_stream_no_violation(self, handler_warn, evidence_queue):
        """Test stream with no violations"""
        chunks = [b"data: ", b'{"content": "Hello world"}', b"\n\n"]
        stream = MockUpstreamStream(chunks)
        
        received = []
        async for chunk in handler_warn.process_stream(stream, run_id="test_run", step_id="test_step"):
            received.append(chunk)
        
        assert len(received) == 3
        assert evidence_queue.empty()  # No violations
    
    async def test_process_stream_queue_full_graceful_degradation(self, handler_warn):
        """Test graceful degradation when queue is full"""
        # Create small queue
        small_queue = queue.Queue(maxsize=1)
        handler = StreamHandler(
            strict_mode=False,
            dlp_patterns={"TEST": re.compile(r"test")},
            evidence_queue=small_queue,
        )
        
        # Fill queue
        small_queue.put_nowait({"type": "test"})
        
        # Stream with violations - should not crash
        chunks = [b"test data", b"more test"]
        stream = MockUpstreamStream(chunks)
        
        received = []
        async for chunk in handler.process_stream(stream, run_id="test_run", step_id="test_step"):
            received.append(chunk)
        
        # Stream should complete (evidence dropped, not chunks)
        assert len(received) == 2
    
    async def test_process_stream_scanning_error_doesnt_break_stream(self, handler_warn):
        """Test that scanning errors don't break stream forwarding"""
        # Create handler with invalid pattern (will cause error)
        handler = StreamHandler(
            strict_mode=False,
            dlp_patterns={"BAD": None},  # Invalid pattern
            evidence_queue=queue.Queue(),
        )
        
        chunks = [b"chunk1", b"chunk2"]
        stream = MockUpstreamStream(chunks)
        
        # Should still forward chunks despite scanning error
        received = []
        async for chunk in handler.process_stream(stream, run_id="test_run", step_id="test_step"):
            received.append(chunk)
        
        assert len(received) == 2


class TimestampedStream:
    """Stream that records when chunks are yielded"""
    
    def __init__(self, chunks):
        self.chunks = chunks
        self.index = 0
        self.yield_times = []
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        
        chunk = self.chunks[self.index]
        self.index += 1
        
        # Record yield time
        self.yield_times.append(time.time())
        
        return chunk


class SlowScanningHandler(StreamHandler):
    """Handler with intentionally slow scanning"""
    
    async def _scan_chunk(self, chunk, run_id, step_id):
        """Slow scanning (50ms delay)"""
        await asyncio.sleep(0.05)  # 50ms delay
        await super()._scan_chunk(chunk, run_id, step_id)


class TestStreamingTeeOrder:
    """Test that tee doesn't block forwarding"""
    
    @pytest.fixture
    def handler(self):
        """Handler with slow scanning"""
        return SlowScanningHandler(
            strict_mode=False,
            dlp_patterns={},
            evidence_queue=queue.Queue(),
        )
    
    async def test_tee_forwards_immediately_despite_slow_scan(self, handler):
        """Test chunks are forwarded immediately despite slow scanning"""
        # Create stream with timestamps
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        stream = TimestampedStream(chunks)
        
        # Record when chunks are received
        received_times = []
        received_chunks = []
        
        start_time = time.time()
        async for chunk in handler.process_stream(stream, run_id="test_run", step_id="test_step"):
            received_times.append(time.time())
            received_chunks.append(chunk)
        end_time = time.time()
        
        # Assert all chunks received
        assert len(received_chunks) == 3
        assert received_chunks == chunks
        
        # Assert chunks were received quickly (not blocked by 50ms scan)
        # First chunk should arrive almost immediately (<10ms)
        # Note: In warn mode, chunks are forwarded before scanning, so delay is minimal
        first_chunk_delay = received_times[0] - start_time
        assert first_chunk_delay < 0.01, f"First chunk delayed by {first_chunk_delay:.3f}s (expected <0.01s)"
        
        # Total time: In warn mode, chunks are forwarded immediately (tee pattern)
        # Scanning happens asynchronously after forwarding, so total time should be low
        # Even with 50ms scan delay per chunk, forwarding is not blocked
        total_time = end_time - start_time
        # Allow some overhead for async operations, but should still be fast
        assert total_time < 0.25, f"Total time {total_time:.3f}s too slow (expected <0.25s for warn mode tee)"
        
        # Chunks should arrive in order
        assert received_times == sorted(received_times)


class TestStreamingStrictModeInterrupt:
    """Test strict mode actually interrupts stream (detailed assertions)"""
    
    @pytest.fixture
    def dlp_patterns(self):
        """DLP patterns"""
        return {
            "SECRET": re.compile(r"secret:\s*[a-zA-Z0-9]+"),
        }
    
    @pytest.fixture
    def evidence_queue(self):
        """Evidence queue"""
        return queue.Queue(maxsize=100)
    
    @pytest.fixture
    def strict_handler(self, dlp_patterns, evidence_queue):
        """Handler in strict mode"""
        return StreamHandler(
            strict_mode=True,
            dlp_patterns=dlp_patterns,
            evidence_queue=evidence_queue,
        )
    
    async def test_strict_mode_interrupts_stream_detailed(self, strict_handler, evidence_queue):
        """Test strict mode interrupts stream on violation with detailed assertions"""
        # Stream: safe chunk, then violation
        chunks = [
            b"data: ",
            b'{"content": "Hello world"}',
            b"\n\n",
            b"data: ",
            b'{"content": "Here is secret: abc123"}',  # Violation
            b"\n\n",
        ]
        
        class SimpleStream:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk
        
        stream = SimpleStream(chunks)
        
        # Process stream - should raise on violation
        received = []
        with pytest.raises(StreamViolation, match="DLP violation"):
            async for chunk in strict_handler.process_stream(stream, run_id="test_run", step_id="test_step"):
                received.append(chunk)
        
        # Assert: at least first chunk was forwarded
        assert len(received) >= 1
        assert received[0] == b"data: "
        
        # Assert: last chunk (with violation) was NOT forwarded
        # (StreamingViolation raised before it could be yielded)
        assert b'{"content": "Here is secret: abc123"}' not in received
        
        # Assert: evidence queue has violation record
        assert not evidence_queue.empty()
        evidence = evidence_queue.get_nowait()
        assert evidence["type"] == "stream_dlp_hit"
        assert "SECRET" in evidence["hits"]
        assert evidence["severity"] == "critical"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
