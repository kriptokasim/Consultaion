"""Prometheus metrics for Consultaion.

Provides standardized counters, histograms, and gauges for
request lifecycle, LLM operations, billing, and SSE streams.
Uses prometheus_client with a lazy singleton.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    REGISTRY = CollectorRegistry(auto_describe=True)

    # ── HTTP Request Metrics ──────────────────────────────────────────────
    HTTP_REQUESTS_TOTAL = Counter(
        "consultaion_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
        registry=REGISTRY,
    )
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "consultaion_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "path"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
        registry=REGISTRY,
    )

    # ── LLM Operation Metrics ─────────────────────────────────────────────
    LLM_REQUESTS_TOTAL = Counter(
        "consultaion_llm_requests_total",
        "Total LLM inference requests",
        ["provider", "model", "operation_class"],
        registry=REGISTRY,
    )
    LLM_REQUEST_DURATION_SECONDS = Histogram(
        "consultaion_llm_request_duration_seconds",
        "LLM inference latency in seconds",
        ["provider", "model"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        registry=REGISTRY,
    )
    LLM_TOKENS_TOTAL = Counter(
        "consultaion_llm_tokens_total",
        "Total LLM tokens consumed",
        ["provider", "model", "direction"],
        registry=REGISTRY,
    )

    # ── Debate / Run Metrics ───────────────────────────────────────────────
    DEBATE_RUNS_TOTAL = Counter(
        "consultaion_debate_runs_total",
        "Total debate/run operations",
        ["mode", "status"],
        registry=REGISTRY,
    )
    DEBATE_RUN_DURATION_SECONDS = Histogram(
        "consultaion_debate_run_duration_seconds",
        "End-to-end debate/run duration in seconds",
        ["mode"],
        buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
        registry=REGISTRY,
    )

    # ── Billing Metrics ────────────────────────────────────────────────────
    BILLING_WEBHOOKS_TOTAL = Counter(
        "consultaion_billing_webhooks_total",
        "Total billing webhook events received",
        ["provider", "event_type", "status"],
        registry=REGISTRY,
    )
    BILLING_CHECKOUTS_TOTAL = Counter(
        "consultaion_billing_checkouts_total",
        "Total checkout sessions created",
        ["plan_slug", "status"],
        registry=REGISTRY,
    )

    # ── SSE Stream Metrics ─────────────────────────────────────────────────
    SSE_STREAMS_ACTIVE = Gauge(
        "consultaion_sse_streams_active",
        "Number of active SSE streams",
        registry=REGISTRY,
    )
    SSE_MESSAGES_TOTAL = Counter(
        "consultaion_sse_messages_total",
        "Total SSE messages published",
        ["channel_type"],
        registry=REGISTRY,
    )

    # ── Rate Limit Metrics ─────────────────────────────────────────────────
    RATE_LIMIT_EXCEEDED_TOTAL = Counter(
        "consultaion_rate_limit_exceeded_total",
        "Total rate limit rejections",
        ["limit_type", "backend"],
        registry=REGISTRY,
    )

    # ── System Health ──────────────────────────────────────────────────────
    DB_POOL_SIZE = Gauge(
        "consultaion_db_pool_size",
        "Active database connection pool size",
        registry=REGISTRY,
    )
    DB_POOL_CHECKED_OUT = Gauge(
        "consultaion_db_pool_checked_out",
        "Checked-out database connections",
        registry=REGISTRY,
    )
    REDIS_POOL_SIZE = Gauge(
        "consultaion_redis_pool_size",
        "Active Redis connection pool size",
        registry=REGISTRY,
    )

    PROMETHEUS_AVAILABLE = True

except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed; metrics endpoint disabled")

    class _Stub:
        def __getattr__(self, name: str):
            raise RuntimeError("prometheus_client is not installed")

    REGISTRY = _Stub()  # type: ignore


def get_metrics_bytes() -> Optional[bytes]:
    """Return the current metrics snapshot as Prometheus text exposition."""
    if not PROMETHEUS_AVAILABLE:
        return None
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    if not PROMETHEUS_AVAILABLE:
        return "text/plain"
    return CONTENT_TYPE_LATEST


def record_http_request(method: str, path: str, status: int, duration: float) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)


def record_llm_request(provider: str, model: str, operation_class: str, duration: float, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    LLM_REQUESTS_TOTAL.labels(provider=provider, model=model, operation_class=operation_class).inc()
    LLM_REQUEST_DURATION_SECONDS.labels(provider=provider, model=model).observe(duration)
    if prompt_tokens > 0:
        LLM_TOKENS_TOTAL.labels(provider=provider, model=model, direction="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        LLM_TOKENS_TOTAL.labels(provider=provider, model=model, direction="completion").inc(completion_tokens)


def record_debate_run(mode: str, status: str, duration: float) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    DEBATE_RUNS_TOTAL.labels(mode=mode, status=status).inc()
    DEBATE_RUN_DURATION_SECONDS.labels(mode=mode).observe(duration)


def record_billing_webhook(provider: str, event_type: str, status: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    BILLING_WEBHOOKS_TOTAL.labels(provider=provider, event_type=event_type, status=status).inc()


def record_billing_checkout(plan_slug: str, status: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    BILLING_CHECKOUTS_TOTAL.labels(plan_slug=plan_slug, status=status).inc()


def record_rate_limit_exceeded(limit_type: str, backend: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    RATE_LIMIT_EXCEEDED_TOTAL.labels(limit_type=limit_type, backend=backend).inc()
