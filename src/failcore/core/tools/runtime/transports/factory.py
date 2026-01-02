from __future__ import annotations

from typing import Any, Mapping

from failcore.core.tools.runtime.transports import BaseTransport


class TransportFactoryError(RuntimeError):
    pass


class TransportFactory:
    """
    Create transports from config without leaking infra dependencies
    into core runtime.

    Design principles:
    - Lazy import infra transports (MCP / Proxy) to avoid import cycles.
    - Config-driven: no hard-coded globals.
    - Fail fast on unknown transport types.
    """

    @staticmethod
    def create(config: Mapping[str, Any]) -> BaseTransport:
        """
        Create a BaseTransport from config.

        Expected config shape (example):

        {
            "type": "mcp",
            "mcp": {
                "session": {
                    "command": ["node", "server.js"],
                    "cwd": "...",
                    "env": {...}
                },
                "list_tools_method": "tools/list",
                "call_tool_method": "tools/call",
                "provider": "mcp",
                "server_version": "0.1"
            }
        }

        Or for proxy (future):

        {
            "type": "proxy",
            "proxy": {
                ...
            }
        }
        """
        if not isinstance(config, Mapping):
            raise TransportFactoryError("transport config must be a mapping")

        t = config.get("type")
        if not t:
            raise TransportFactoryError("transport config missing 'type'")

        if t == "mcp":
            return TransportFactory._create_mcp(config)

        if t == "proxy":
            return TransportFactory._create_proxy(config)

        raise TransportFactoryError(f"unknown transport type: {t}")

    # =========================================================
    # MCP
    # =========================================================

    @staticmethod
    def _create_mcp(config: Mapping[str, Any]) -> BaseTransport:
        try:
            from failcore.adapters.mcp.transport import (
                McpTransport,
                McpTransportConfig,
            )
            from failcore.adapters.mcp.session import (
                McpSessionConfig,
            )
        except Exception as e:
            raise TransportFactoryError(
                f"failed to import MCP transport: {e}"
            ) from e

        mcp_cfg = config.get("mcp")
        if not isinstance(mcp_cfg, Mapping):
            raise TransportFactoryError("mcp transport requires 'mcp' mapping")

        session_cfg = mcp_cfg.get("session")
        if not isinstance(session_cfg, Mapping):
            raise TransportFactoryError("mcp.session must be a mapping")

        try:
            session = McpSessionConfig(
                command=list(session_cfg["command"]),
                cwd=session_cfg.get("cwd"),
                env=session_cfg.get("env"),
                startup_timeout_s=session_cfg.get("startup_timeout_s", 10.0),
                request_timeout_s=session_cfg.get("request_timeout_s", 60.0),
                max_restarts=session_cfg.get("max_restarts", 3),
                restart_backoff_s=session_cfg.get("restart_backoff_s", 0.5),
                serialize_requests=session_cfg.get("serialize_requests", True),
            )
        except KeyError as e:
            raise TransportFactoryError(
                f"missing required mcp.session field: {e}"
            ) from e

        transport_cfg = McpTransportConfig(
            session=session,
            list_tools_method=mcp_cfg.get("list_tools_method", "tools/list"),
            call_tool_method=mcp_cfg.get("call_tool_method", "tools/call"),
            provider=mcp_cfg.get("provider", "mcp"),
            server_version=mcp_cfg.get("server_version"),
        )

        return McpTransport(transport_cfg)

    # =========================================================
    # Proxy (future)
    # =========================================================

    @staticmethod
    def _create_proxy(config: Mapping[str, Any]) -> BaseTransport:
        try:
            from failcore.adapters.proxy.transport import ProxyTransport
        except Exception as e:
            raise TransportFactoryError(
                f"failed to import Proxy transport: {e}"
            ) from e

        proxy_cfg = config.get("proxy")
        if not isinstance(proxy_cfg, Mapping):
            raise TransportFactoryError("proxy transport requires 'proxy' mapping")

        # We intentionally do not assume ProxyTransport's config shape yet.
        # Pass raw config through to keep this factory stable.
        return ProxyTransport(proxy_cfg)
