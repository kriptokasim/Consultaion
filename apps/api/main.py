import asyncio
import logging.config
import uuid
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from auth import CSRF_COOKIE_NAME, ENABLE_CSRF
from billing.routes import billing_router
from promotions.routes import promotions_router
from database import engine, init_db
from config import settings
from log_config import LOGGING_CONFIG, clear_log_context, reset_request_id, set_request_id
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
from routes.admin import admin_ops_summary, admin_router, admin_logs, admin_users, update_ratings_endpoint
from schemas import DebateCreate
from sse_backend import get_sse_backend

root_level = settings.LOG_LEVEL.upper()
LOGGING_CONFIG["loggers"][""]["level"] = root_level
for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "apps"):
    if logger_name in LOGGING_CONFIG["loggers"]:
        LOGGING_CONFIG["loggers"][logger_name]["level"] = root_level
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

SENTRY_DSN = settings.SENTRY_DSN
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=settings.SENTRY_ENV,
        traces_sample_rate=float(settings.SENTRY_SAMPLE_RATE),
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
ENABLE_SEC_HEADERS = settings.ENABLE_SEC_HEADERS


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
        ensure_rate_limiter_ready(raise_on_failure=settings.RATE_LIMIT_BACKEND == "redis")
    except Exception as exc:
        logger.error("Rate limiter backend check failed: %s", exc)
        if not settings.IS_LOCAL_ENV:
            raise
    try:
        models = list_enabled_models()
        if not models:
            logger.error("No models enabled; configure provider API keys.")
        else:
            logger.info("Models enabled: %s (default=%s)", [m.id for m in models], get_default_model().id)
    except Exception as exc:
        logger.error("Model registry initialization failed: %s", exc)
    cleanup_task: asyncio.Task | None = None
    try:
        cleanup_task = asyncio.create_task(_sse_cleanup_loop())
    except RuntimeError:
        cleanup_task = None
    try:
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task


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
    worker_env = settings.WEB_CONCURRENCY or settings.GUNICORN_WORKERS
    try:
        if worker_env and int(worker_env) > 1 and settings.SSE_BACKEND.lower() == "memory":
            logger.warning(
                "SSE_BACKEND=memory; running with %s workers may cause /debates/{id}/stream to miss events. "
                "Switch to SSE_BACKEND=redis for multi-worker deployments.",
                worker_env,
            )
    except ValueError:
        return


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clear_log_context()
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
            clear_log_context()
        response.headers["X-Request-ID"] = request_id
        return response


origins = settings.CORS_ORIGINS.split(",")
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
app.include_router(billing_router)
app.include_router(promotions_router)


# Lifespan helpers
async def _sse_cleanup_loop() -> None:
    backend = get_sse_backend()
    try:
        while True:
            await backend.cleanup()
            await asyncio.sleep(settings.SSE_CHANNEL_TTL_SECONDS)
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
    "billing_router",
    "promotions_router",
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
    "admin_ops_summary",
    "update_ratings_endpoint",
]
