# failcore/gateways/__init__.py
"""
Gateways - Deployable data plane services

This layer contains ASGI/HTTP servers and other deployable services that:
- Accept external requests (HTTP, WebSocket, etc.)
- Route through core business logic
- Compose infrastructure implementations

Architecture principle: gateways/ can import from core/ and infrastructure/
"""
