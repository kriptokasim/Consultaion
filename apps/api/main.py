import asyncio
import logging.config
import uuid
from contextlib import asynccontextmanager, suppress

from auth import CSRF_COOKIE_NAME, ENABLE_CSRF
from billing.routes import billing_router
from config import settings
from database import init_db
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from log_config import LOGGING_CONFIG, clear_log_context, reset_request_id, set_request_id
from parliament.model_registry import get_default_model, list_enabled_models
from promotions.routes import promotions_router
from ratelimit import ensure_rate_limiter_ready
from routes.admin import (
    admin_logs,
    admin_ops_summary,
    admin_router,
    admin_users,
    update_ratings_endpoint,
)
from routes.api_keys import api_keys_router
from routes.auth import (
    AuthRequest,
    auth_router,
    get_me,
    google_callback,
    google_login,
    login_user,
    logout_user,
    register_user,
)
from routes.debates import (
    DebateUpdate,
    create_debate,
    debates_router,
    export_debate_report,
    export_scores_csv,
    get_debate,
    get_debate_events,
    get_debate_judges,
    get_debate_report,
    get_leaderboard,
    get_leaderboard_persona,
    list_debates,
    start_debate_run,
    stream_events,
    update_debate,
)
from routes.models import models_router
from routes.stats import (
    get_debate_summary,
    get_hall_of_fame_stats,
    get_model_detail,
    get_model_leaderboard_stats,
    get_rate_limit_snapshot,
    get_system_health,
    healthz,
    readyz,
    stats_router,
)
from routes.teams import (
    TeamCreate,
    TeamMemberCreate,
    add_team_member,
    create_team,
    list_team_members,
    list_teams,
    teams_router,
)
from schemas import DebateCreate
from schemas import DebateCreate
from sse_backend import get_sse_backend
from starlette.middleware.base import BaseHTTPMiddleware

root_level = settings.LOG_LEVEL.upper()
LOGGING_CONFIG["loggers"][""]["level"] = root_level
for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "apps"):
    if logger_name in LOGGING_CONFIG["loggers"]:
        LOGGING_CONFIG["loggers"][logger_name]["level"] = root_level
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
TEST_FAST_APP = settings.ENV == "test"
if TEST_FAST_APP:

    try:
        from database import reset_engine as _reset_engine
    except ImportError:
        logger.warning("TEST_FAST_APP enabled but reset_engine is not available")
    else:
        try:
            _reset_engine()
        except Exception as exc:
            logger.error("Failed to reset DB engine in TEST_FAST_APP mode", exc_info=exc)
            raise

SENTRY_DSN = settings.SENTRY_DSN
# Only initialize Sentry if DSN is set to a valid, non-empty value
if SENTRY_DSN and SENTRY_DSN.strip() and SENTRY_DSN.strip().startswith("http"):
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=settings.SENTRY_ENV,
            traces_sample_rate=float(settings.SENTRY_SAMPLE_RATE),
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        )
        logger.info("Sentry initialized successfully")
    except Exception as e:
        logger.warning("Failed to initialize Sentry: %s. Continuing without Sentry.", e)
else:
    logger.info("Sentry DSN not configured or invalid. Skipping Sentry initialization.")


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
    if TEST_FAST_APP:
        yield
        return
    init_db()
    # Verify that critical tables exist; fail fast if missing
    try:
        from sqlalchemy import create_engine, inspect
        engine = create_engine(settings.DATABASE_URL)
        critical_tables = {
            "user",
            "team_member",
            "usage_quota",
            "usage_counter",
            "api_keys",
            "audit_log",
            "debate",
        }
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        missing = [tbl for tbl in critical_tables if tbl not in existing_tables]

        if missing:
            msg = f"Missing critical tables: {', '.join(missing)}"
            logger.error(msg)
            raise RuntimeError(msg)
    except Exception as e:
        logger.error("Database schema verification failed: %s", e)
        raise

    # Verify migration version matches code
    try:
        from alembic import config, script
        from alembic.migration import MigrationContext
        
        # Assume alembic.ini is in the root or accessible
        alembic_cfg = config.Config("alembic.ini") 
        # We need to set the script location relative to where we are or use absolute path
        # If alembic.ini relies on recursive search or specific paths, this might be tricky.
        # Simplification: Just verify alembic_version table is readable and has a revision.
        with engine.connect() as connection:
             context = MigrationContext.configure(connection)
             current_rev = context.get_current_revision()
             logger.info(f"Current database revision: {current_rev}")
             if not current_rev:
                 logger.warning("Database has no migration revision! Changes may be missing.")
    except Exception as e:
        logger.warning(f"Could not verify migration version: {e}")
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
    
    # Initialize and start SSE backend (singleton)
    sse_backend = get_sse_backend()
    await sse_backend.start()
    app.state.sse_backend = sse_backend
    
    # Patchset 66.0: Start stale debate cleanup loop
    from orchestrator_cleanup import start_cleanup_loop, stop_cleanup_loop
    cleanup_task = start_cleanup_loop()
    
    try:
        yield
    finally:
        # Patchset 66.0: Stop cleanup loop gracefully
        stop_cleanup_loop()
        if cleanup_task and not cleanup_task.done():
            with suppress(asyncio.CancelledError):
                await cleanup_task
        await sse_backend.stop()



app = FastAPI(
    title="Consultaion API",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[] if TEST_FAST_APP else [Depends(csrf_protect)],
)

if ENABLE_SEC_HEADERS and not TEST_FAST_APP:

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
if settings.ENV != "test":
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

from exceptions import AppError


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.error(
        "AppError",
        extra={
            "code": exc.code,
            "details": exc.details,
            "status_code": exc.status_code,
            "request_path": request.url.path,
            "request_method": request.method,
            "request_id": request.headers.get("x-request-id"),
            "user_id": getattr(request.state, "user_id", None),
        },
    )
    error_payload = {
        "code": exc.code,
        "message": exc.message,
        "details": exc.details,
        "hint": exc.hint,
        "retryable": exc.retryable,
    }
    # Add retry_after_seconds for rate limit errors
    if hasattr(exc, "retry_after_seconds") and exc.retry_after_seconds is not None:
        error_payload["retry_after_seconds"] = exc.retry_after_seconds
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_payload},
    )


# Domain routers live in apps/api/routes/*
from routes.debug import router as debug_router  # Patchset 53.0

app.include_router(auth_router)
app.include_router(stats_router)
app.include_router(models_router)
app.include_router(debates_router)
app.include_router(teams_router)
app.include_router(admin_router)

# Patchset 53.0: Debug routes (only active when AUTH_DEBUG=True)
app.include_router(debug_router)

# Import and add routing admin router
from routes.routing_admin import router as routing_admin_router

app.include_router(routing_admin_router)

app.include_router(billing_router)
app.include_router(promotions_router)
app.include_router(api_keys_router)

from routes.features import router as features_router
from routes.gifs import router as gifs_router

app.include_router(gifs_router, prefix="/gifs", tags=["gifs"])
app.include_router(features_router)


# Lifespan helpers


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
