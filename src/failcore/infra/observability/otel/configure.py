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
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
    except Exception:
        # OTel not installed
        return None

    service_name = (
        _getenv("OTEL_SERVICE_NAME")
        or _getenv("FAILCORE_OTEL_SERVICE_NAME")
        or "failcore"
    )

    endpoint = _getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    insecure = _truthy(_getenv("OTEL_EXPORTER_OTLP_INSECURE"))

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=insecure,
    )

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    return trace.get_tracer("failcore")
