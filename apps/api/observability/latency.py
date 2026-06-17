"""Streaming latency budgets and telemetry for Consultaion.

FH108: Prometheus histogram metrics for run lifecycle timing, model connection,
TTFT (time to first token), and end-to-end streaming latency.

Usage:
    from observability.latency import record_run_latency, record_ttft, PROMETHEUS_AVAILABLE
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Histogram

    PROMETHEUS_AVAILABLE = True

    RUN_ACCEPT_LATENCY = Histogram(
        "consultaion_run_accept_latency_seconds",
        "Time from run creation to first worker pickup",
        ["mode"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    )

    RUN_QUEUE_WAIT = Histogram(
        "consultaion_run_queue_wait_seconds",
        "Time a run spends waiting in the queue before execution",
        ["mode", "queue"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )

    MODEL_CONNECT_LATENCY = Histogram(
        "consultaion_model_connect_latency_seconds",
        "Time from model call start to first bytes received from provider",
        ["provider", "model_family"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0),
    )

    MODEL_TTFT = Histogram(
        "consultaion_model_ttft_seconds",
        "Time to first token from provider",
        ["provider", "model_family"],
        buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0),
    )

    MODEL_TOTAL_LATENCY = Histogram(
        "consultaion_model_total_latency_seconds",
        "Total time for a single model call (connect to completion)",
        ["provider", "model_family", "success"],
        buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
    )

    STREAM_TOTAL_DURATION = Histogram(
        "consultaion_stream_total_duration_seconds",
        "End-to-end duration of a streaming response",
        ["provider", "result"],
        buckets=(1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0),
    )

    STREAM_DPS = Histogram(
        "consultaion_stream_deltas_per_second",
        "Deltas per second during streaming",
        ["provider"],
        buckets=(1.0, 5.0, 10.0, 20.0, 50.0, 100.0),
    )

except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.debug("prometheus_client not installed — streaming latency metrics disabled")


def record_run_latency(mode: str, seconds: float) -> None:
    if PROMETHEUS_AVAILABLE:
        RUN_ACCEPT_LATENCY.labels(mode=mode).observe(seconds)


def record_queue_wait(mode: str, queue: str, seconds: float) -> None:
    if PROMETHEUS_AVAILABLE:
        RUN_QUEUE_WAIT.labels(mode=mode, queue=queue).observe(seconds)


def record_connect_latency(provider: str, model_family: str, seconds: float) -> None:
    if PROMETHEUS_AVAILABLE:
        MODEL_CONNECT_LATENCY.labels(provider=provider, model_family=model_family).observe(seconds)


def record_ttft(provider: str, model_family: str, seconds: float) -> None:
    if PROMETHEUS_AVAILABLE:
        MODEL_TTFT.labels(provider=provider, model_family=model_family).observe(seconds)


def record_model_latency(provider: str, model_family: str, success: bool, seconds: float) -> None:
    if PROMETHEUS_AVAILABLE:
        MODEL_TOTAL_LATENCY.labels(
            provider=provider,
            model_family=model_family,
            success=str(success).lower(),
        ).observe(seconds)


def record_stream_duration(provider: str, result: str, seconds: float) -> None:
    if PROMETHEUS_AVAILABLE:
        STREAM_TOTAL_DURATION.labels(provider=provider, result=result).observe(seconds)


def record_stream_dps(provider: str, dps: float) -> None:
    if PROMETHEUS_AVAILABLE:
        STREAM_DPS.labels(provider=provider).observe(dps)


class TimerContext:
    """Simple context manager for timing code blocks."""

    def __init__(self):
        self.start: float = 0
        self.elapsed: float = 0

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, *_):
        self.elapsed = time.monotonic() - self.start
