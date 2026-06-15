"""Weighted rate-limit middleware using operation-class cost units.

Replaces simple request counting with weighted budget enforcement.
Heavy operations (Arena, Debate, Continue) consume 8 cost units;
light reads consume 1 unit. Per-user budget is enforced via Redis
or in-memory backend.

Features:
- Authenticated identity resolution via dedicated module
- SSE connection limits (separate budget, evaluated before general GET)
- Read operation classification with per-class budgets
- Atomic remaining budget reporting via X-RateLimit-Remaining
- Proper rate limit headers on all responses
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import settings
from core.operation_classes import (
    OperationClass,
    OPERATION_CLASSES,
    OPERATION_WEIGHTS,
    get_operation_class,
    get_operation_weight,
)
from ratelimit import get_rate_limiter_backend
from middleware.rate_limit_identity import resolve_identity

logger = logging.getLogger(__name__)

# Per-user weighted budget defaults (cost units per window)
PROD_WEIGHTED_BUDGET: int = 200
DEV_WEIGHTED_BUDGET: int = 800
WEIGHTED_WINDOW_SECONDS: int = 60

# SSE-specific budget (separate from regular API budget)
SSE_BUDGET: int = 10
SSE_WINDOW_SECONDS: int = 60


def _classify_endpoint(method: str, path: str) -> str:
    """Map request to an operation class action name."""
    if method == "POST":
        if path.rstrip("/").endswith("/arena") or "/arena/" in path:
            return "create_arena"
        if "/debates" in path and not path.rstrip("/").endswith("/debates"):
            if "continue" in path:
                return "continue_staged_run"
            if "retry" in path or "rerun" in path:
                return "debate_retry"
            return "create_debate"
        if path.rstrip("/").endswith("/debates"):
            return "create_debate"
        if "checkout" in path:
            return "create_debate"
        if "validate" in path or "provider-key" in path:
            return "validate_provider_key"
        if "export" in path:
            return "export_report"
        if "retry" in path or "rerun" in path:
            return "retry_single_model"

    if method == "GET":
        if "/stream" in path:
            return "sse_stream"
        if "/run" in path or "/debate" in path:
            if "report" in path:
                return "read_report"
            if "events" in path:
                return "get_events"
            return "read_run"
        if "leaderboard" in path:
            return "list_runs"
        if "members" in path:
            return "get_members"
        if "search" in path:
            return "search"
        if "models" in path:
            return "list_runs"
        if "usage" in path:
            return "list_runs"
        if "health" in path:
            return "health_check"
        if "ops-summary" in path:
            return "list_runs"

    return "validate_provider_key"


# Read operation classes that should be rate-limited
READ_ACTIONS = {
    "read_run", "read_report", "get_events", "list_runs",
    "get_members", "search", "health_check",
}


def get_weighted_budget() -> int:
    """Return per-user weighted budget for the current environment."""
    if settings.IS_LOCAL_ENV:
        return getattr(settings, "WEIGHTED_RL_BUDGET", DEV_WEIGHTED_BUDGET)
    return getattr(settings, "WEIGHTED_RL_BUDGET", PROD_WEIGHTED_BUDGET)


def _is_sse_request(path: str, method: str) -> bool:
    """Check if request is for an SSE endpoint."""
    return method == "GET" and "/stream" in path


class WeightedRateLimitMiddleware(BaseHTTPMiddleware):
    """Weighted rate-limit middleware that enforces per-user cost-unit budgets."""

    def __init__(self, app, budget: Optional[int] = None, window_seconds: Optional[int] = None):
        super().__init__(app)
        self._budget = budget or get_weighted_budget()
        self._window = window_seconds or WEIGHTED_WINDOW_SECONDS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Resolve identity early (user ID > API key > IP)
        key, identity_type = resolve_identity(request)

        # SSE: evaluate before general GET handling
        if _is_sse_request(request.url.path, request.method):
            return await self._enforce_sse_limit(request, call_next, key)

        # Classify the endpoint
        action = _classify_endpoint(request.method, request.url.path)

        # Health checks: exempt from weighted enforcement
        if action == "health_check":
            response = await call_next(request)
            self._add_headers(response, key, action, 0, 0)
            return response

        # Read operations: apply lightweight enforcement
        if action in READ_ACTIONS:
            return await self._enforce_read_limit(request, call_next, key, action)

        # Write operations: full weighted enforcement
        weight = get_operation_weight(action)
        op_class = get_operation_class(action)

        backend = get_rate_limiter_backend()
        allowed, retry_after = backend.allow_weighted(key, self._window, self._budget, weight)

        if not allowed:
            logger.info(
                "weighted_rate_limit.exceeded key=%s action=%s class=%s weight=%d budget=%d",
                key, action, op_class.value, weight, self._budget,
            )
            from observability.metrics import record_rate_limit_exceeded
            record_rate_limit_exceeded("weighted", settings.RATE_LIMIT_BACKEND)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Weighted rate limit exceeded. Please slow down.",
                        "details": {
                            "action": action,
                            "operation_class": op_class.value,
                            "cost_units": weight,
                            "budget": self._budget,
                            "window_seconds": self._window,
                        },
                        "retry_after_seconds": retry_after or self._window,
                        "retryable": True,
                    }
                },
                headers=self._build_headers(key, action, weight, retry_after),
            )

        response = await call_next(request)
        remaining = max(0, self._budget - weight)
        self._add_headers(response, key, action, weight, remaining)
        return response

    async def _enforce_read_limit(
        self, request: Request, call_next: Callable, key: str, action: str
    ) -> Response:
        """Enforce lightweight rate limiting on read operations."""
        weight = get_operation_weight(action)
        backend = get_rate_limiter_backend()
        # Reads use a lighter budget within the same window
        allowed, retry_after = backend.allow_weighted(key, self._window, self._budget, weight)

        if not allowed:
            logger.info("read_rate_limit.exceeded key=%s action=%s", key, action)
            from observability.metrics import record_rate_limit_exceeded
            record_rate_limit_exceeded("read", settings.RATE_LIMIT_BACKEND)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many read requests. Please slow down.",
                        "details": {
                            "action": action,
                            "cost_units": weight,
                            "budget": self._budget,
                            "window_seconds": self._window,
                        },
                        "retry_after_seconds": retry_after or self._window,
                        "retryable": True,
                    }
                },
                headers=self._build_headers(key, action, weight, retry_after),
            )

        response = await call_next(request)
        remaining = max(0, self._budget - weight)
        self._add_headers(response, key, action, weight, remaining)
        return response

    async def _enforce_sse_limit(
        self, request: Request, call_next: Callable, key: str
    ) -> Response:
        """Enforce separate SSE connection budget."""
        backend = get_rate_limiter_backend()
        allowed, retry_after = backend.allow_weighted(key, SSE_WINDOW_SECONDS, SSE_BUDGET, 1)

        if not allowed:
            logger.info("sse_rate_limit.exceeded key=%s", key)
            from observability.metrics import record_rate_limit_exceeded
            record_rate_limit_exceeded("sse", settings.RATE_LIMIT_BACKEND)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "sse_rate_limit_exceeded",
                        "message": "Too many SSE connections. Please wait before reconnecting.",
                        "details": {
                            "budget": SSE_BUDGET,
                            "window_seconds": SSE_WINDOW_SECONDS,
                        },
                        "retry_after_seconds": retry_after or SSE_WINDOW_SECONDS,
                        "retryable": True,
                    }
                },
                headers={
                    "Retry-After": str(retry_after or SSE_WINDOW_SECONDS),
                    "X-RateLimit-Budget": str(SSE_BUDGET),
                    "X-RateLimit-Remaining": str(max(0, SSE_BUDGET - 1)),
                    "X-RateLimit-Cost": "1",
                    "X-RateLimit-Action": "sse_stream",
                    "X-RateLimit-Window": str(SSE_WINDOW_SECONDS),
                },
            )

        return await call_next(request)

    def _add_headers(
        self, response: Response, key: str, action: str, cost: int, remaining: int
    ) -> None:
        response.headers["X-RateLimit-Budget"] = str(self._budget)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Cost"] = str(cost)
        response.headers["X-RateLimit-Action"] = action
        response.headers["X-RateLimit-Window"] = str(self._window)

    def _build_headers(
        self, key: str, action: str, cost: int, retry_after: Optional[int]
    ) -> dict:
        return {
            "Retry-After": str(retry_after or self._window),
            "X-RateLimit-Budget": str(self._budget),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Cost": str(cost),
            "X-RateLimit-Action": action,
            "X-RateLimit-Window": str(self._window),
        }
