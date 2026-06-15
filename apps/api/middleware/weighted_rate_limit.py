"""Weighted rate-limit middleware using operation-class cost units.

Replaces simple request counting with weighted budget enforcement.
Heavy operations (Arena, Debate, Continue) consume 8 cost units;
light reads consume 1 unit. Per-user budget is enforced via Redis
or in-memory backend.
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

logger = logging.getLogger(__name__)

# Per-user weighted budget defaults (cost units per window)
PROD_WEIGHTED_BUDGET: int = 200
DEV_WEIGHTED_BUDGET: int = 800
WEIGHTED_WINDOW_SECONDS: int = 60


def _classify_endpoint(method: str, path: str) -> str:
    """Map request to an operation class action name."""
    # Arena / Debate creation
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
            return "create_debate"  # billing checkout is medium
        if "validate" in path or "provider-key" in path:
            return "validate_provider_key"
        if "export" in path:
            return "export_report"
        if "retry" in path or "rerun" in path:
            return "retry_single_model"

    # Reads
    if method == "GET":
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
            return "list_runs"
        if "ops-summary" in path:
            return "list_runs"

    # Default: medium
    return "validate_provider_key"


def get_weighted_budget() -> int:
    """Return per-user weighted budget for the current environment."""
    if settings.IS_LOCAL_ENV:
        return getattr(settings, "WEIGHTED_RL_BUDGET", DEV_WEIGHTED_BUDGET)
    return getattr(settings, "WEIGHTED_RL_BUDGET", PROD_WEIGHTED_BUDGET)


class WeightedRateLimitMiddleware(BaseHTTPMiddleware):
    """Weighted rate-limit middleware that enforces per-user cost-unit budgets."""

    def __init__(self, app, budget: Optional[int] = None, window_seconds: Optional[int] = None):
        super().__init__(app)
        self._budget = budget or get_weighted_budget()
        self._window = window_seconds or WEIGHTED_WINDOW_SECONDS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for safe methods on read-only endpoints
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Extract user identity (anonymous fallback to IP)
        user_id = getattr(request.state, "user_id", None)
        ip = request.client.host if request.client else "unknown"
        key = f"wl:{user_id}" if user_id else f"wl:{ip}"

        action = _classify_endpoint(request.method, request.url.path)
        weight = get_operation_weight(action)
        op_class = get_operation_class(action)

        backend = get_rate_limiter_backend()
        allowed, retry_after = backend.allow_weighted(key, self._window, self._budget, weight)

        if not allowed:
            logger.info(
                "weighted_rate_limit.exceeded user=%s action=%s class=%s weight=%d budget=%d",
                user_id or ip, action, op_class.value, weight, self._budget,
            )
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
                headers={"Retry-After": str(retry_after or self._window)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Budget"] = str(self._budget)
        response.headers["X-RateLimit-Action"] = action
        response.headers["X-RateLimit-Cost"] = str(weight)
        return response
