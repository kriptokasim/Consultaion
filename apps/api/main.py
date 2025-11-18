import asyncio
import logging.config
import os
import uuid
from contextlib import asynccontextmanager, suppress
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from auth import CSRF_COOKIE_NAME, ENABLE_CSRF
from database import engine, init_db
from deps import get_current_user
from log_config import LOGGING_CONFIG, reset_request_id, set_request_id
from ratelimit import ensure_rate_limiter_ready
from model_registry import list_enabled_models, get_default_model
from routes.auth import (
    auth_router,
    AuthRequest,
    get_me,
    login_user,
    logout_user,
    register_user,
    google_login,
    google_callback,
)
from routes.models import models_router
from routes.stats import (
    stats_router,
    DebateSummary,
    HealthSnapshot,
    ModelStatsDetail,
    ModelStatsSummary,
    RateLimitSnapshot,
    get_debate_summary,
    get_hall_of_fame_stats,
    get_model_detail,
    get_model_leaderboard_stats,
    get_rate_limit_snapshot,
    get_system_health,
    healthz,
    readyz,
)
from routes.debates import (
    debates_router,
    DebateUpdate,
    CHANNELS,
    CHANNEL_META,
    CHANNEL_TTL_SECS,
    CHANNEL_SWEEP_INTERVAL,
    sweep_stale_channels,
    create_debate,
    list_debates,
    get_debate,
    start_debate_run,
    export_scores_csv,
    get_debate_report,
    export_debate_report,
    get_debate_events,
    get_debate_judges,
    stream_events,
    update_debate,
    get_leaderboard,
    get_leaderboard_persona,
)
from routes.teams import teams_router, TeamCreate, TeamMemberCreate, create_team, list_teams, list_team_members, add_team_member
from routes.admin import admin_router, admin_logs, admin_users, update_ratings_endpoint
from schemas import DebateCreate

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENV", "local"),
        traces_sample_rate=float(os.getenv("SENTRY_SAMPLE_RATE", "0.1")),
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
ENABLE_SEC_HEADERS = os.getenv("ENABLE_SEC_HEADERS", "1").strip().lower() not in {"0", "false", "no"}


async def csrf_protect(request: Request) -> None:
    """Optional double-submit CSRF guard for cookie auth."""
    if request.method in SAFE_METHODS or not ENABLE_CSRF:
        return
    if request.url.path in {"/auth/login", "/auth/register"}:
        return
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _warn_on_multi_worker()
    try:
        ensure_rate_limiter_ready(raise_on_failure=os.getenv("RATE_LIMIT_BACKEND", "memory") == "redis")
    except Exception as exc:
        logger.error("Rate limiter backend check failed: %s", exc)
    try:
        models = list_enabled_models()
        if not models:
            logger.error("No models enabled; configure provider API keys.")
        else:
            logger.info("Models enabled: %s (default=%s)", [m.id for m in models], get_default_model().id)
    except Exception as exc:
        logger.error("Model registry initialization failed: %s", exc)
    sweeper_task: asyncio.Task | None = None
    try:
        sweeper_task = asyncio.create_task(_channel_sweeper_loop())
    except RuntimeError:
        sweeper_task = None
    try:
        yield
    finally:
        if sweeper_task:
            sweeper_task.cancel()
            with suppress(asyncio.CancelledError):
                await sweeper_task


app = FastAPI(
    title="Consultaion API",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(csrf_protect)],
)

if ENABLE_SEC_HEADERS:

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "0")
        return response


def _warn_on_multi_worker() -> None:
    """Warn if multiple workers are in use while SSE queues are process-local."""
    worker_env = os.getenv("WEB_CONCURRENCY") or os.getenv("GUNICORN_WORKERS")
    try:
        if worker_env and int(worker_env) > 1:
            logger.warning(
                "SSE queues are process-local; running with %s workers may cause /debates/{id}/stream to miss events. "
                "Use a single worker or move SSE to a shared backend.",
                worker_env,
            )
    except ValueError:
        return


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        return response


origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain routers live in apps/api/routes/*
app.include_router(auth_router)
app.include_router(stats_router)
app.include_router(models_router)
app.include_router(debates_router)
app.include_router(teams_router)
app.include_router(admin_router)


# Lifespan helpers
async def _channel_sweeper_loop() -> None:
    try:
        while True:
            sweep_stale_channels()
            await asyncio.sleep(CHANNEL_SWEEP_INTERVAL)
    except asyncio.CancelledError:
        raise


__all__ = [
    # routers (for compatibility/imports)
    "auth_router",
    "stats_router",
    "models_router",
    "debates_router",
    "teams_router",
    "admin_router",
    # exported handlers for legacy imports/tests
    "AuthRequest",
    "get_me",
    "login_user",
    "logout_user",
    "register_user",
    "google_login",
    "google_callback",
    "healthz",
    "readyz",
    "get_model_leaderboard_stats",
    "get_model_detail",
    "get_debate_summary",
    "get_rate_limit_snapshot",
    "get_system_health",
    "get_hall_of_fame_stats",
    "get_debate_report",
    "export_debate_report",
    "get_debate_events",
    "get_debate_judges",
    "export_scores_csv",
    "stream_events",
    "create_debate",
    "DebateCreate",
    "DebateUpdate",
    "list_debates",
    "get_debate",
    "start_debate_run",
    "get_leaderboard",
    "get_leaderboard_persona",
    "update_debate",
    "TeamCreate",
    "TeamMemberCreate",
    "create_team",
    "list_teams",
    "list_team_members",
    "add_team_member",
    "admin_users",
    "admin_logs",
    "update_ratings_endpoint",
    # channel state
    "CHANNELS",
    "CHANNEL_META",
    "CHANNEL_TTL_SECS",
    "CHANNEL_SWEEP_INTERVAL",
    "sweep_stale_channels",
]
