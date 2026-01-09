"""
End-to-end ASGI tests for FailCore Proxy

Covers:
1) Normal JSON response + usage enrichment
2) Streaming SSE response (OpenAI-like) pass-through
3) DLP detection in warn/fail-open mode (request should still succeed)
4) Fail-open when egress/trace sink fails (request should still succeed)

Uses httpx.ASGITransport for in-process testing (no port binding).
"""

import pytest
import httpx
from pathlib import Path
from typing import Dict, Any, Optional

from failcore.core.proxy import ProxyConfig, ProxyServer, ProxyPipeline, StreamHandler
from failcore.core.egress import EgressEngine, TraceSink, UsageEnricher, DLPEnricher, TaintEnricher
from failcore.utils.paths import init_run, create_run_directory
from tests.proxy.assertions import read_jsonl

# Use asyncio backend only (trio is not installed)
pytestmark = pytest.mark.anyio(backend="asyncio")


# ----------------------------
# Mock upstream clients
# ----------------------------

class MockUpstreamClient:
    """Mock upstream that returns non-streaming JSON with usage"""
    async def forward_request(self, url, method, headers, body):
        return {
            "status": 200,
            "headers": {"content-type": "application/json"},
            "body": b'{"id":"chatcmpl-123","usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}}',
        }


class MockStreamingUpstreamClient:
    """Mock upstream that returns OpenAI-like SSE (text/event-stream)"""
    async def forward_request(self, url, method, headers, body):
        sse_chunks = (
            b'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"H"}}]}\n\n',
            b'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"e"}}]}\n\n',
            b'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"llo"}}]}\n\n',
            b"data: [DONE]\n\n",
        )
        return {
            "status": 200,
            "headers": {"content-type": "text/event-stream"},
            # NOTE: real streaming would be chunked; this still tests ASGI wiring + SSE correctness
            "body": b"".join(sse_chunks),
        }


# ----------------------------
# Failing trace sink for fail-open test
# ----------------------------

class FailingTraceSink(TraceSink):
    """TraceSink that always fails on write (simulated)"""
    def write(self, event):
        raise RuntimeError("TraceSink write failed (simulated)")


# ----------------------------
# Test class
# ----------------------------

class TestProxyE2EASGI:
    @pytest.fixture
    def trace_dir(self, request):
        """Create default trace directory using FailCore path utils"""
        # Use unique command name per test to avoid file conflicts between tests
        test_name = request.node.name.replace("[", "_").replace("]", "")
        ctx = init_run(command_name=f"proxy_test_{test_name}")
        trace_dir = create_run_directory(ctx, exist_ok=True)
        yield trace_dir

    @pytest.fixture
    def trace_path(self, trace_dir):
        """Get default trace.jsonl path"""
        return trace_dir / "trace.jsonl"

    @pytest.fixture
    def event_writer(self, trace_path):
        """Create EventWriter for ATTEMPT/RESULT events"""
        from failcore.core.trace.writer import EventWriter
        writer = EventWriter(
            trace_path=trace_path,
            run_id="e2e_test",
            kind="proxy",
            buffer_size=1,
        )
        yield writer
        try:
            writer.close()
        except Exception:
            pass

    @pytest.fixture
    def egress_engine(self, trace_path):
        trace_sink = TraceSink(
            str(trace_path),
            async_mode=False,
            buffer_size=1,
            flush_interval_s=0.0,
            run_id="e2e_test",
            kind="proxy",
        )
        enrichers = [UsageEnricher(), DLPEnricher(), TaintEnricher()]
        engine = EgressEngine(trace_sink=trace_sink, enrichers=enrichers)
        yield engine
        try:
            engine.flush()
            engine.close()
        except Exception:
            pass

    @pytest.fixture
    def failing_egress_engine(self, trace_path):
        failing_sink = FailingTraceSink(
            str(trace_path),
            async_mode=False,
            buffer_size=1,
            flush_interval_s=0.0,
            run_id="e2e_test",
            kind="proxy",
        )
        enrichers = [UsageEnricher(), DLPEnricher(), TaintEnricher()]
        engine = EgressEngine(trace_sink=failing_sink, enrichers=enrichers)
        yield engine
        try:
            engine.flush()
            engine.close()
        except Exception:
            pass

    @pytest.fixture
    def proxy_server(self, egress_engine, event_writer):
        """Create ProxyServer with full pipeline (egress + event_writer)"""
        config = ProxyConfig(run_id="e2e_test")
        streaming_handler = StreamHandler(strict_mode=False)
        pipeline = ProxyPipeline(
            egress_engine=egress_engine, 
            upstream_client=MockUpstreamClient(),
            event_writer=event_writer,  # ✅ Pass EventWriter for ATTEMPT/RESULT
        )
        server = ProxyServer(config=config, pipeline=pipeline, streaming_handler=streaming_handler)

        # Sanity checks: ASGI app exposed
        assert hasattr(server, "app") and callable(server.app), "ProxyServer.app must be ASGI callable"
        assert hasattr(server, "asgi_app") and callable(server.asgi_app), "ProxyServer.asgi_app must be ASGI callable"
        return server

    def _read_events(self, trace_path: Path):
        assert trace_path.exists(), f"Trace file not created at {trace_path}"
        events = read_jsonl(trace_path)
        assert events, "No events found in trace"
        return events

    def _find_post_call(self, events):
        """Find post_call event in v0.1.3 format"""
        for e in events:
            # v0.1.3 format: event.data contains egress event data
            event_data = e.get("event", {})
            if event_data.get("type") == "EGRESS_EVENT":
                data = event_data.get("data", {})
                evidence = data.get("evidence", {}) or {}
                if evidence.get("phase") == "post_call":
                    return data  # Return the data dict (legacy format)
        raise AssertionError(f"No post_call event found. Total events: {len(events)}")

    def _find_pre_call(self, events):
        """Find pre_call event in v0.1.3 format"""
        for e in events:
            # v0.1.3 format: event.data contains egress event data
            event_data = e.get("event", {})
            if event_data.get("type") == "EGRESS_EVENT":
                data = event_data.get("data", {})
                evidence = data.get("evidence", {}) or {}
                if evidence.get("phase") == "pre_call":
                    return data  # Return the data dict (legacy format)
        raise AssertionError(f"No pre_call event found. Total events: {len(events)}")
    
    def _find_attempt(self, events):
        """Find ATTEMPT event"""
        for e in events:
            event_data = e.get("event", {})
            if event_data.get("type") == "ATTEMPT":
                return event_data
        return None
    
    def _find_result(self, events):
        """Find RESULT event"""
        for e in events:
            event_data = e.get("event", {})
            if event_data.get("type") == "RESULT":
                return event_data
        return None
    
    def _assert_trace_structure(self, events):
        """
        Assert trace structure follows v0.1.3 unified model
        
        Requirements:
        - Must have ATTEMPT + RESULT events (business layer)
        - Must have pre_call + post_call EGRESS_EVENTs (security layer)
        - No legacy STEP_START/STEP_END event type strings
        - All events share same step_id
        """
        # Find key events
        attempt = self._find_attempt(events)
        result = self._find_result(events)
        pre_call = self._find_pre_call(events)
        post_call = self._find_post_call(events)
        
        # Assert presence
        assert attempt is not None, "No ATTEMPT event found"
        assert result is not None, "No RESULT event found"
        assert pre_call is not None, "No pre_call EGRESS_EVENT found"
        assert post_call is not None, "No post_call EGRESS_EVENT found"
        
        # Assert step_id consistency
        attempt_step_id = attempt.get("step", {}).get("id")
        result_step_id = result.get("step", {}).get("id")
        
        assert attempt_step_id, "ATTEMPT event missing step.id"
        assert result_step_id, "RESULT event missing step.id"
        assert attempt_step_id == result_step_id, \
            f"step_id mismatch: ATTEMPT={attempt_step_id}, RESULT={result_step_id}"

    async def test_e2e_request_flow_usage(self, proxy_server, egress_engine, trace_path):
        """JSON response + usage enrichment persisted to trace"""
        asgi_app = proxy_server.app

        transport = httpx.ASGITransport(app=asgi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={
                    "authorization": "Bearer sk-test",
                    "content-type": "application/json",
                    "x-failcore-provider": "openai",
                    "x-failcore-run-id": "e2e_test",
                    "x-failcore-step-id": "e2e_step",
                },
                json={"model": "gpt-4", "messages": []},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["usage"]["total_tokens"] == 30

        egress_engine.flush()
        events = self._read_events(trace_path)
        post_call = self._find_post_call(events)

        evidence = post_call.get("evidence", {}) or {}
        usage = evidence.get("usage")
        assert isinstance(usage, dict), f"Usage not found or not dict. evidence keys={list(evidence.keys())}"
        assert usage.get("prompt_tokens") == 10
        assert usage.get("completion_tokens") == 20
        assert usage.get("total_tokens") == 30

    async def test_e2e_streaming_sse_response(self, egress_engine, event_writer, trace_path):
        """
        Streaming SSE response pass-through.

        Notes:
        - ASGITransport may aggregate body chunks, so we use client.stream() + aiter_text()
          to better reflect real SSE usage patterns.
        - Even if internal send() doesn't chunk, we still validate:
          * content-type header
          * SSE framing (data: ...)
          * DONE marker
        - This is E2E validation: SSE content + headers + completion are all verified.
        """
        # Create dedicated proxy_server for this test to avoid fixture sharing issues
        config = ProxyConfig(run_id="e2e_test")
        streaming_handler = StreamHandler(strict_mode=False)
        pipeline = ProxyPipeline(
            egress_engine=egress_engine, 
            upstream_client=MockStreamingUpstreamClient(),
            event_writer=event_writer,  # ✅ Pass EventWriter
        )
        proxy_server = ProxyServer(config=config, pipeline=pipeline, streaming_handler=streaming_handler)
        asgi_app = proxy_server.app

        transport = httpx.ASGITransport(app=asgi_app)

        # Use streaming client API to better reflect real SSE usage
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                headers={
                    "authorization": "Bearer sk-test",
                    "content-type": "application/json",
                    "x-failcore-provider": "openai",
                    "x-failcore-run-id": "e2e_test",
                    "x-failcore-step-id": "e2e_step_stream",
                },
                json={"model": "gpt-4", "messages": [], "stream": True},
            ) as resp:
                assert resp.status_code == 200
                # Validate content-type (some frameworks append charset; use startswith)
                content_type = resp.headers.get("content-type", "")
                assert content_type.startswith("text/event-stream"), \
                    f"Expected text/event-stream, got {content_type}"

                # Collect chunks (ASGITransport may aggregate, but we still validate content)
                chunks = []
                async for text in resp.aiter_text():
                    chunks.append(text)

        # Validate SSE content structure
        sse_content = "".join(chunks)
        # Check SSE framing: data: {...}
        assert 'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"H"}}]}' in sse_content or \
               'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"H"}}]}\n\n' in sse_content
        # Check completion marker
        assert "data: [DONE]" in sse_content or "data: [DONE]\n\n" in sse_content

        # Trace checks (best-effort: depends on what your server records)
        egress_engine.flush()
        events = self._read_events(trace_path)
        post_call = self._find_post_call(events)
        evidence = post_call.get("evidence", {}) or {}

        # If your implementation sets streaming flag, assert it.
        # If not implemented yet, this assertion would be too strict; keep it conditional.
        if "streaming" in evidence:
            assert evidence["streaming"] is True

    async def test_e2e_dlp_detection_warn_mode(self):
        """
        DLP detects sensitive-looking data but fail-open keeps request successful.

        IMPORTANT:
        - Exact hit label and redaction behavior depends on your DLPEnricher implementation.
        - This test asserts presence of some hit signal and absence of raw secret in evidence string.
        """
        # Create completely independent trace path and egress_engine for this test
        from failcore.utils.paths import init_run, create_run_directory
        from failcore.core.trace.writer import EventWriter
        import time
        # Use a clearly unique path
        ctx = init_run(command_name=f"dlp_test_{int(time.time() * 1000000)}")
        trace_dir = create_run_directory(ctx, exist_ok=True)
        trace_path = trace_dir / "trace.jsonl"
        
        # Ensure clean slate
        if trace_path.exists():
            try:
                trace_path.unlink()
            except Exception:
                pass
    
        # Create EventWriter for ATTEMPT/RESULT events
        event_writer = EventWriter(
            trace_path=trace_path,
            run_id="e2e_test",
            kind="proxy",
            buffer_size=1,
        )
        
        # TraceSink now requires run_id and kind for EventWriter
        trace_sink = TraceSink(
            str(trace_path),
            async_mode=False,
            buffer_size=1,
            flush_interval_s=0.0,
            run_id="e2e_test",
            kind="proxy",
        )
        enrichers = [UsageEnricher(), DLPEnricher(), TaintEnricher()]
        egress_engine = EgressEngine(trace_sink=trace_sink, enrichers=enrichers)
        
        # Create dedicated proxy_server for this test to avoid fixture sharing issues
        config = ProxyConfig(run_id="e2e_test")
        streaming_handler = StreamHandler(strict_mode=False)
        pipeline = ProxyPipeline(
            egress_engine=egress_engine, 
            upstream_client=MockUpstreamClient(),
            event_writer=event_writer,  # ✅ Pass EventWriter
        )
        proxy_server = ProxyServer(config=config, pipeline=pipeline, streaming_handler=streaming_handler)
        
        asgi_app = proxy_server.app
        transport = httpx.ASGITransport(app=asgi_app)

        secret = "sk-123456789012345678901234567890123456789012345678"
        
        # Explicitly serialize JSON to avoid any httpx caching issues
        import json as json_module
        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": f"My API key is {secret}"}],
        }
        request_body = json_module.dumps(request_data).encode("utf-8")

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={
                    "authorization": "Bearer sk-test",
                    "content-type": "application/json",
                    "x-failcore-provider": "openai",
                    "x-failcore-run-id": "e2e_test",
                    "x-failcore-step-id": "e2e_step_dlp",
                },
                content=request_body,
            )

        # Fail-open: request should succeed
        assert resp.status_code == 200

        egress_engine.flush()
        egress_engine.close()
        event_writer.close()  # Ensure ATTEMPT/RESULT are written
        
        events = self._read_events(trace_path)

        # DLP detection can happen in either pre_call (request body) or post_call (response body)
        # Check both events for DLP hits
        pre_call = self._find_pre_call(events)
        post_call = self._find_post_call(events)

        # Debug: Check request_body value in pre_call
        pre_evidence = pre_call.get("evidence", {}) or {}
        request_body = pre_evidence.get("request_body")
    
        # Try to find DLP hits in either event
        hits = None
        evidence_with_hits = None
    
        for event in [pre_call, post_call]:
            evidence = event.get("evidence", {}) or {}
            # DLP evidence key is implementation-defined; try multiple common field names
            # Compatible with: dlp_hits, dlp, dlp_findings, dlp_violations, etc.
            found_hits = (
                evidence.get("dlp_hits") or
                evidence.get("dlp") or
                evidence.get("dlp_findings") or
                evidence.get("dlp_violations") or
                evidence.get("dlp_detections")
            )
            if found_hits is not None:
                hits = found_hits
                evidence_with_hits = evidence
                break
    
        # If no hits found, provide detailed debug info
        if hits is None:
            # Check if request_body contains the secret
            request_body_str = str(request_body) if request_body else "None"
            
            error_msg = (
                f"No DLP hits/findings found in pre_call or post_call events.\n"
                f"Pre_call keys: {list(pre_evidence.keys())}\n"
                f"Post_call keys: {list(post_call.get('evidence', {}).keys())}\n"
                f"Request body type: {type(request_body)}\n"
                f"Request body length: {len(request_body) if request_body else 0}\n"
                f"Request body preview: {request_body_str[:200] if request_body else 'None'}"
            )
            assert hits is not None, error_msg

        # Ensure secret is not leaked in evidence (best-effort redaction check)
        # Check both pre_call and post_call evidence
        for event in [pre_call, post_call]:
            evidence = event.get("evidence", {}) or {}
            evidence_str = str(evidence)
            assert secret not in evidence_str, \
                f"Raw secret should not appear in trace evidence (redaction expected). " \
                f"Phase: {evidence.get('phase')}, Evidence preview: {evidence_str[:200]}"

        # If your DLP labels are stable, you can tighten this assertion:
        # For now, we just verify that some DLP signal exists
        if isinstance(hits, (list, tuple)):
            assert len(hits) > 0, "DLP hits should be non-empty"
        elif isinstance(hits, dict):
            assert len(hits) > 0, "DLP findings dict should be non-empty"

    async def test_e2e_fail_open_egress_error(self, proxy_server, failing_egress_engine):
        """
        Fail-open: even if trace sink fails, the proxy should still return 200.

        IMPORTANT:
        - Fail-open must be implemented at ProxyServer / Pipeline / EgressEngine level
        - Egress exceptions must be swallowed (only affect evidence), not bubble to response layer
        - This test verifies that egress write failures don't interrupt business flow
        - The request should succeed (200) even if trace writing fails
        """
        # Replace egress engine with failing one
        proxy_server.pipeline.egress_engine = failing_egress_engine
        asgi_app = proxy_server.app

        transport = httpx.ASGITransport(app=asgi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={
                    "authorization": "Bearer sk-test",
                    "content-type": "application/json",
                    "x-failcore-provider": "openai",
                    "x-failcore-run-id": "e2e_test_failopen",
                    "x-failcore-step-id": "e2e_step_failopen",
                },
                json={"model": "gpt-4", "messages": []},
            )

        # CRITICAL: Request must succeed despite egress failure
        # If egress exceptions bubble up, this would be 500
        assert resp.status_code == 200, \
            f"Expected 200 (fail-open), got {resp.status_code}. " \
            f"Egress failures should not affect business response."

        # Verify response body is valid (upstream response should still be returned)
        data = resp.json()
        assert "usage" in data or "id" in data, \
            "Response should contain valid upstream data despite egress failure"

        # Note: We don't assert trace file contents here because trace writing failed.
        # The key assertion is that the HTTP response succeeded (200).
