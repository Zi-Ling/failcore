# failcore/gateways/proxy/server.py
"""
Proxy gateway server - ASGI HTTP endpoint for LLM provider interception

This is a deployable gateway service that composes core business logic.
"""

from typing import Optional, Any, Dict, Callable
import asyncio

from failcore.config.proxy import ProxyConfig
from failcore.core.proxy import ProxyPipeline, StreamHandler


class ProxyServer:
    """
    HTTP proxy server for LLM provider requests
    
    Responsibilities:
    - Accept HTTP requests
    - Route through ProxyPipeline
    - Handle streaming responses
    - Emit unified egress events
    
    Design:
    - Built on asyncio
    - Fail-open on errors
    - Transparent forwarding
    """
    
    def __init__(
        self,
        config: ProxyConfig,
        pipeline: Optional[ProxyPipeline] = None,
        streaming_handler: Optional[StreamHandler] = None,
    ):
        self.config = config
        self.pipeline = pipeline or ProxyPipeline()
        self.streaming_handler = streaming_handler or StreamHandler(
            strict_mode=config.streaming_strict_mode
        )
        self._server: Optional[Any] = None
        
        # Expose ASGI app for test/production use
        self.app: Callable = self._create_asgi_app()
        self.asgi_app: Callable = self.app  # Alias for clarity
    
    async def start(self) -> None:
        """Start proxy server"""
        # Future: implement actual HTTP server
        # For now, placeholder
        print(f"Proxy server starting on {self.config.host}:{self.config.port}")
        
        # Keep server running
        while True:
            await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop proxy server"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
    
    def _create_asgi_app(self) -> Callable:
        """
        Create ASGI application
        
        Returns a standard ASGI3 callable (scope, receive, send) -> awaitable.
        This app handles HTTP requests and routes them through the proxy pipeline.
        """
        async def app(scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
            """ASGI3 application callable"""
            if scope["type"] != "http":
                # Only handle HTTP requests
                await send({
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [[b"content-type", b"text/plain"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"Only HTTP requests are supported",
                })
                return
            
            # Extract request metadata
            method = scope["method"]
            path = scope.get("path", "/")
            raw_headers = scope.get("headers", [])
            
            # Parse headers
            headers: Dict[str, str] = {}
            for k, v in raw_headers:
                try:
                    headers[k.decode("latin-1").lower()] = v.decode("latin-1")
                except Exception:
                    pass  # Skip malformed headers
            
            # Read request body (ASGI may send body in chunks)
            # IMPORTANT: ASGI spec allows body to be sent in multiple messages
            # We must keep reading until more_body is False
            # The first http.request message may have body bytes, and subsequent
            # messages will have more_body=True until the last one (more_body=False)
            body = b""
            while True:
                message = await receive()
                msg_type = message.get("type")
                
                if msg_type == "http.request":
                    # Get body chunk (may be empty on first message, but usually contains data)
                    chunk = message.get("body", b"")
                    if chunk:
                        body += chunk
                    # Check if more body is coming
                    more_body = message.get("more_body", False)
                    if not more_body:
                        # No more body chunks - we're done
                        break
                    # If more_body is True, continue reading next chunk
                elif msg_type == "http.disconnect":
                    # Client disconnected before body was fully received
                    break
                else:
                    # Unknown message type - log and break to avoid infinite loop
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Unexpected ASGI message type: {msg_type}")
                    break
            
            
            # Extract proxy metadata from headers
            provider = headers.get("x-failcore-provider", "openai")
            run_id = headers.get("x-failcore-run-id") or self.config.run_id or "proxy_default"
            step_id = headers.get("x-failcore-step-id", f"proxy_{id(self)}")
            
            # Process request through pipeline
            try:
                result = await self.pipeline.process_request(
                    provider=provider,
                    endpoint=path,
                    method=method,
                    headers=headers,
                    body=body,
                    run_id=run_id,
                    step_id=step_id,
                )
                
                # Extract response
                status = result.get("status", 200)
                response_headers = result.get("headers", {})
                response_body = result.get("body", b"")
                
                # Ensure body is bytes
                if isinstance(response_body, str):
                    response_body = response_body.encode("utf-8")
                elif not isinstance(response_body, bytes):
                    response_body = b""
                
                # Convert headers to ASGI format
                asgi_headers = []
                for k, v in response_headers.items():
                    asgi_headers.append((
                        k.encode("latin-1") if isinstance(k, str) else k,
                        str(v).encode("latin-1")
                    ))
                
                # Send response
                await send({
                    "type": "http.response.start",
                    "status": status,
                    "headers": asgi_headers,
                })
                await send({
                    "type": "http.response.body",
                    "body": response_body,
                })
            
            except Exception as e:
                # Fail-open: return 500 but don't crash
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Proxy request failed: {e}")
                
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [[b"content-type", b"text/plain"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"Internal proxy error",
                })
        
        return app
    
    async def handle_request(
        self,
        provider: str,
        endpoint: str,
        method: str,
        headers: dict,
        body: Optional[bytes],
    ) -> dict:
        """
        Handle proxy request
        
        Routes through pipeline for unified processing.
        """
        run_id = self.config.run_id or "proxy_default"
        step_id = f"proxy_{id(self)}"
        
        return await self.pipeline.process_request(
            provider, endpoint, method, headers, body, run_id, step_id
        )


__all__ = ["ProxyServer"]
