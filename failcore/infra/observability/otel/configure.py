from __future__ import annotations

from typing import Optional


def _getenv(name: str) -> Optional[str]:
    import os
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v or None


def _truthy(v: Optional[str]) -> bool:
    if v is None:
        return False
    return v.lower() in {"1", "true", "yes", "y", "on"}


def try_create_tracer():
    """
    Try to create an OpenTelemetry tracer based on environment variables.

    Enable rules:
      - FAILCORE_OTEL=1
      - OR OTEL_EXPORTER_OTLP_ENDPOINT is set

    Transport priority (user can override via OTEL_EXPORTER_OTLP_PROTOCOL):
      1. HTTP (default, lightweight, no C extensions)
      2. gRPC (if explicitly requested)

    Returns:
      tracer or None (if OTel is disabled or unavailable)
    """
    enabled = _truthy(_getenv("FAILCORE_OTEL")) or (
        _getenv("OTEL_EXPORTER_OTLP_ENDPOINT") is not None
    )
    if not enabled:
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        # OTel SDK not installed
        return None

    # Determine protocol (http or grpc)
    protocol = _getenv("OTEL_EXPORTER_OTLP_PROTOCOL") or "http/protobuf"
    
    # Try to import exporter based on protocol
    exporter = None
    if "grpc" in protocol.lower():
        # User explicitly wants gRPC (high-performance scenarios)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter_type = "grpc"
        except ImportError:
            # gRPC exporter not installed, fallback to HTTP
            exporter = None
    
    if exporter is None:
        # Default: HTTP exporter (recommended, lightweight)
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter_type = "http"
        except ImportError:
            # HTTP exporter not installed either
            return None

    service_name = (
        _getenv("OTEL_SERVICE_NAME")
        or _getenv("FAILCORE_OTEL_SERVICE_NAME")
        or "failcore"
    )

    endpoint = _getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    # HTTP-specific: endpoint needs /v1/traces suffix if not present
    if exporter_type == "http" and endpoint and not endpoint.endswith("/v1/traces"):
        if not endpoint.endswith("/"):
            endpoint += "/"
        endpoint += "v1/traces"

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # Create exporter with appropriate settings
    exporter_kwargs = {"endpoint": endpoint}
    
    # gRPC-specific: insecure flag
    if exporter_type == "grpc":
        insecure = _truthy(_getenv("OTEL_EXPORTER_OTLP_INSECURE"))
        exporter_kwargs["insecure"] = insecure

    try:
        exporter_instance = OTLPSpanExporter(**exporter_kwargs)
        provider.add_span_processor(BatchSpanProcessor(exporter_instance))
        trace.set_tracer_provider(provider)
        return trace.get_tracer("failcore")
    except Exception:
        # Exporter initialization failed (e.g., invalid endpoint)
        return None
