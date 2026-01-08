# failcore/hooks/httpx_patch.py
"""
HTTPX monkey-patch - Emit EgressEvent for all HTTP requests

Patches httpx.Client and httpx.AsyncClient to intercept requests.
"""

from typing import Optional, Any
import time

from failcore.core.egress import EgressEngine, EgressEvent, EgressType, PolicyDecision, RiskLevel


_original_httpx_request = None
_original_httpx_async_request = None
_egress_engine: Optional[EgressEngine] = None


def patch_httpx(egress_engine: EgressEngine) -> None:
    """
    Patch httpx to emit egress events
    
    Args:
        egress_engine: EgressEngine for event routing
    """
    global _egress_engine, _original_httpx_request, _original_httpx_async_request
    
    try:
        import httpx
    except ImportError:
        # httpx not installed, skip patch
        return
    
    _egress_engine = egress_engine
    
    # Patch sync client
    if hasattr(httpx.Client, 'request'):
        _original_httpx_request = httpx.Client.request
        httpx.Client.request = _patched_httpx_request
    
    # Patch async client
    if hasattr(httpx.AsyncClient, 'request'):
        _original_httpx_async_request = httpx.AsyncClient.request
        httpx.AsyncClient.request = _patched_httpx_async_request


def unpatch_httpx() -> None:
    """Restore original httpx methods"""
    global _egress_engine, _original_httpx_request, _original_httpx_async_request
    
    try:
        import httpx
    except ImportError:
        return
    
    if _original_httpx_request:
        httpx.Client.request = _original_httpx_request
        _original_httpx_request = None
    
    if _original_httpx_async_request:
        httpx.AsyncClient.request = _original_httpx_async_request
        _original_httpx_async_request = None
    
    _egress_engine = None


def _patched_httpx_request(self, method: str, url: Any, **kwargs):
    """Patched httpx.Client.request"""
    start_time = time.time()
    run_id = "httpx_hook"
    step_id = f"http_{id(self)}_{int(start_time * 1000)}"
    
    # Emit pre-call event
    if _egress_engine:
        _emit_http_event(method, str(url), run_id, step_id, "pre_call")
    
    # Call original
    try:
        response = _original_httpx_request(self, method, url, **kwargs)
        
        # Emit post-call event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_http_event(method, str(url), run_id, step_id, "post_call", 
                           response={"status": response.status_code}, duration_ms=duration_ms)
        
        return response
    except Exception as e:
        # Emit error event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_http_event(method, str(url), run_id, step_id, "post_call",
                           error={"type": type(e).__name__, "message": str(e)}, duration_ms=duration_ms)
        raise


async def _patched_httpx_async_request(self, method: str, url: Any, **kwargs):
    """Patched httpx.AsyncClient.request"""
    start_time = time.time()
    run_id = "httpx_hook"
    step_id = f"http_{id(self)}_{int(start_time * 1000)}"
    
    # Emit pre-call event
    if _egress_engine:
        _emit_http_event(method, str(url), run_id, step_id, "pre_call")
    
    # Call original
    try:
        response = await _original_httpx_async_request(self, method, url, **kwargs)
        
        # Emit post-call event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_http_event(method, str(url), run_id, step_id, "post_call",
                           response={"status": response.status_code}, duration_ms=duration_ms)
        
        return response
    except Exception as e:
        # Emit error event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_http_event(method, str(url), run_id, step_id, "post_call",
                           error={"type": type(e).__name__, "message": str(e)}, duration_ms=duration_ms)
        raise


def _emit_http_event(
    method: str, 
    url: str, 
    run_id: str, 
    step_id: str, 
    phase: str,
    response: Optional[dict] = None,
    error: Optional[dict] = None,
    duration_ms: float = 0,
) -> None:
    """Emit HTTP egress event"""
    if not _egress_engine:
        return
    
    event = EgressEvent(
        egress=EgressType.NETWORK,
        action=f"httpx.{method.lower()}",
        target=url,
        run_id=run_id,
        step_id=step_id,
        tool_name="httpx_hook",
        decision=PolicyDecision.ALLOW if not error else PolicyDecision.DENY,
        risk=RiskLevel.LOW if not error else RiskLevel.MEDIUM,
        evidence={
            "method": method,
            "url": url,
            "phase": phase,
            "response": response,
            "error": error,
            "duration_ms": duration_ms,
        },
    )
    
    try:
        _egress_engine.emit(event)
    except Exception:
        # Hook emission must not break user code
        pass


__all__ = ["patch_httpx", "unpatch_httpx"]
