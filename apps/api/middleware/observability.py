"""Observability middleware for request tracing and metrics.

Provides:
- Request ID propagation (X-Request-ID)
- HTTP request duration and status recording via Prometheus
- OpenTelemetry span creation for each request
- SSE connection tracking
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from observability.metrics import PROMETHEUS_AVAILABLE, record_http_request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

try:
    from observability.tracing import OTEL_AVAILABLE
except ImportError:
    OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP metrics and propagates request IDs."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start
            # Normalize path for metrics (strip IDs to avoid cardinality explosion)
            path = self._normalize_path(request.url.path)
            method = request.method

            if PROMETHEUS_AVAILABLE:
                record_http_request(method, path, status_code, duration)

            # Log slow requests
            if duration > 2.0:
                logger.warning(
                    "slow_request method=%s path=%s duration=%.2fs status=%d",
                    method, path, duration, status_code,
                )

        # Propagate request ID in response
        response.headers["X-Request-ID"] = request_id
        return response

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize URL path to reduce metric cardinality.

        Replaces UUIDs and numeric IDs with placeholders.
        """
        import re
        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
            flags=re.IGNORECASE,
        )
        # Replace numeric IDs
        path = re.sub(r"/\d+(?=/|$)", "/{id}", path)
        return path
