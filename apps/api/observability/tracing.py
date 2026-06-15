"""OpenTelemetry tracing initialization.

Provides optional distributed tracing via OpenTelemetry SDK.
When ENABLE_OTEL_TRACING is not set, all functions are no-ops.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from config import settings

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import Span, Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    logger.info("opentelemetry not installed; tracing disabled")


_tracer = None


def init_tracing() -> None:
    """Initialize OpenTelemetry tracer provider if enabled."""
    global _tracer
    if not OTEL_AVAILABLE:
        return
    if not getattr(settings, "ENABLE_OTEL_TRACING", False):
        return

    try:
        resource = Resource.create({
            SERVICE_NAME: "consultaion-api",
            "deployment.environment": settings.APP_ENV,
            "service.version": settings.APP_VERSION,
        })
        provider = TracerProvider(resource=resource)

        # Console exporter for development
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        # OTLP exporter for production (configurable endpoint)
        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info("OTLP exporter configured: endpoint=%s", otlp_endpoint)
            except ImportError:
                logger.warning("OTLP exporter not installed; using console only")

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("consultaion-api")
        logger.info("OpenTelemetry tracing initialized (env=%s)", settings.APP_ENV)
    except Exception as exc:
        logger.warning("Failed to initialize OpenTelemetry: %s", exc)
        _tracer = None


def get_tracer():
    return _tracer


@contextmanager
def traced_span(name: str, attributes: Optional[dict] = None) -> Generator[Optional["Span"], None, None]:
    """Context manager that creates a span if tracing is active."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


def record_llm_span(provider: str, model: str, duration: float, tokens: int = 0) -> None:
    """Record an LLM inference span (called from LLM wrappers)."""
    if _tracer is None:
        return
    with traced_span("llm.inference", {
        "llm.provider": provider,
        "llm.model": model,
        "llm.duration_seconds": duration,
        "llm.tokens": tokens,
    }):
        pass
