# failcore/hooks/requests_patch.py
"""
Requests monkey-patch - Emit EgressEvent for all HTTP requests

Patches requests.Session.request to intercept requests.
"""

from typing import Optional
import time

from failcore.core.egress import EgressEngine, EgressEvent, EgressType, PolicyDecision, RiskLevel


_original_requests_request = None
_egress_engine: Optional[EgressEngine] = None


def patch_requests(egress_engine: EgressEngine) -> None:
    """
    Patch requests to emit egress events
    
    Args:
        egress_engine: EgressEngine for event routing
    """
    global _egress_engine, _original_requests_request
    
    try:
        import requests
    except ImportError:
        # requests not installed, skip patch
        return
    
    _egress_engine = egress_engine
    
    # Patch Session.request (covers all HTTP methods)
    if hasattr(requests.Session, 'request'):
        _original_requests_request = requests.Session.request
        requests.Session.request = _patched_requests_request


def unpatch_requests() -> None:
    """Restore original requests methods"""
    global _egress_engine, _original_requests_request
    
    try:
        import requests
    except ImportError:
        return
    
    if _original_requests_request:
        requests.Session.request = _original_requests_request
        _original_requests_request = None
    
    _egress_engine = None


def _patched_requests_request(self, method: str, url: str, **kwargs):
    """Patched requests.Session.request"""
    start_time = time.time()
    run_id = "requests_hook"
    step_id = f"http_{id(self)}_{int(start_time * 1000)}"
    
    # Emit pre-call event
    if _egress_engine:
        _emit_http_event(method, url, run_id, step_id, "pre_call")
    
    # Call original
    try:
        response = _original_requests_request(self, method, url, **kwargs)
        
        # Emit post-call event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_http_event(method, url, run_id, step_id, "post_call",
                           response={"status": response.status_code}, duration_ms=duration_ms)
        
        return response
    except Exception as e:
        # Emit error event
        if _egress_engine:
            duration_ms = (time.time() - start_time) * 1000
            _emit_http_event(method, url, run_id, step_id, "post_call",
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
        action=f"requests.{method.lower()}",
        target=url,
        run_id=run_id,
        step_id=step_id,
        tool_name="requests_hook",
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


__all__ = ["patch_requests", "unpatch_requests"]
