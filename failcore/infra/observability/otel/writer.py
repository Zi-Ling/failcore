from __future__ import annotations

from typing import Any, Optional

from .configure import try_create_tracer
from .mapping import (
    span_name_from_event,
    attributes_from_event,
    is_error_event,
)


class OtelWriter:
    """
    Writer-compatible OpenTelemetry exporter.

    This class is designed to match FailCore's existing trace writer usage:
      writer.write(event)

    If OTel is unavailable or disabled, this writer should NOT be created.
    """

    def __init__(self, tracer):
        self._tracer = tracer

    @classmethod
    def try_from_env(cls) -> Optional["OtelWriter"]:
        tracer = try_create_tracer()
        if tracer is None:
            return None
        return cls(tracer)

    def write(self, event: Any) -> None:
        """
        Export a single FailCore event as an OTel span.

        This method must never raise.
        """
        try:
            span_name = span_name_from_event(event)
            attrs = attributes_from_event(event)

            with self._tracer.start_as_current_span(span_name) as span:
                for k, v in attrs.items():
                    span.set_attribute(k, v)

                if is_error_event(event):
                    span.set_status(
                        status=span.status.__class__(
                            span.status.StatusCode.ERROR
                        )
                    )
        except Exception:
            # Observability must never affect execution
            return
