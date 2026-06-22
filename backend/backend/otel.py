"""
OpenTelemetry instrumentation for the ZaneOps API.

This wires up tracing for incoming HTTP requests, database queries (psycopg),
redis calls and outgoing HTTP requests so we can troubleshoot performance per
endpoint.

Configuration is driven by settings/env vars:
- ``OTEL_TRACES_ENABLED``  : enable tracing (default: on in DEV, off in PROD)
- ``OTEL_SERVICE_NAME``    : service name reported to the backend (default: ``zane-api``)
- ``OTEL_EXPORTER_OTLP_ENDPOINT`` : OTLP gRPC endpoint (default to ``http://zane.tempo:4317``).
  When unset, spans are printed to the console (useful in DEV without a backend).

This is read natively by the OTel SDK as well, so the standard
``OTEL_EXPORTER_OTLP_*`` env vars keep working.
"""

import logging

from django.conf import settings
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)

logger = logging.getLogger(__name__)

_CONFIGURED = False


def _build_resource() -> Resource:
    return Resource.create(
        {
            SERVICE_NAME: settings.OTEL_SERVICE_NAME,
            SERVICE_VERSION: settings.IMAGE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )


def _build_span_exporter() -> SpanExporter:
    """OTLP gRPC exporter when an endpoint is configured, else console."""
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    print("OTEL_EXPORTER_OTLP_ENDPOINT is not set, exporting traces to the console.")
    return ConsoleSpanExporter()


def configure_opentelemetry() -> None:
    """Idempotently set up the OTel SDK and auto-instrumentations."""
    global _CONFIGURED

    if _CONFIGURED or not settings.OTEL_TRACES_ENABLED:
        return

    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    resource = _build_resource()

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(_build_span_exporter()))
    trace.set_tracer_provider(provider)

    # NOTE: incoming HTTP request (server) spans are created by wrapping the
    # ASGI app in `instrument_asgi_app` (see backend/asgi.py). `DjangoInstrumentor`
    # does not emit server spans when Django is served as a pure-ASGI app under
    # daphne/Channels, so we instrument at the ASGI layer instead.
    #
    # capture SQL statements as span attributes for slow-query troubleshooting
    PsycopgInstrumentor().instrument(enable_commenter=True)
    RedisInstrumentor().instrument()
    RequestsInstrumentor().instrument()

    _CONFIGURED = True
    print(
        "OpenTelemetry tracing enabled (service={}, endpoint={})".format(
            settings.OTEL_SERVICE_NAME,
            settings.OTEL_EXPORTER_OTLP_ENDPOINT or "console",
        ),
    )


def instrument_asgi_app(app):
    """Wrap an ASGI app so inbound HTTP requests produce server spans.

    Must be called after ``configure_opentelemetry`` (which sets the global
    tracer provider). Returns the app unchanged when tracing is disabled.
    """
    if not settings.OTEL_TRACES_ENABLED:
        return app

    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

    return OpenTelemetryMiddleware(app)
