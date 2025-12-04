from __future__ import annotations

import builtins
import logging
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    ENV: str = "development"
    IS_LOCAL_ENV: bool = True

    DATABASE_URL: str = "sqlite:///./consultaion.db"
    REDIS_URL: str | None = None

    RATE_LIMIT_BACKEND: Literal["redis", "memory"] | None = None
    RL_WINDOW: int = 60
    RL_MAX_CALLS: int = 5
    AUTH_RL_WINDOW: int = 300
    AUTH_RL_MAX_CALLS: int = 10

    DEFAULT_MAX_RUNS_PER_HOUR: int = 30
    DEFAULT_MAX_TOKENS_PER_DAY: int = 150000

    DISABLE_AUTORUN: bool = False
    FAST_DEBATE: bool = False
    USE_MOCK: bool = True
    REQUIRE_REAL_LLM: bool = False
    DISABLE_RATINGS: bool = False
    ENABLE_METRICS: bool = True
    APP_VERSION: str = "0.2.0"

    LOG_LEVEL: str = "INFO"
    ENABLE_SEC_HEADERS: bool = False
    CORS_ORIGINS: str = "http://localhost:3000"
    WEB_APP_ORIGIN: str | None = None
    NEXT_PUBLIC_WEB_URL: str | None = None
    NEXT_PUBLIC_APP_URL: str | None = None
    NEXT_PUBLIC_WEB_ORIGIN: str | None = None
    NEXT_PUBLIC_APP_ORIGIN: str | None = None
    NEXT_PUBLIC_SITE_URL: str | None = None
    VERCEL_URL: str | None = None
    NEXT_PUBLIC_VERCEL_URL: str | None = None

    SSE_BACKEND: Literal["memory", "redis"] = "memory"
    SSE_REDIS_URL: str | None = None
    SSE_CHANNEL_TTL_SECONDS: int = 900

    # LLM retry controls
    LLM_RETRY_ENABLED: bool = Field(True, description="Enable retry/backoff around LLM calls.")
    LLM_RETRY_MAX_ATTEMPTS: int = Field(3, ge=1, le=10)
    LLM_RETRY_INITIAL_DELAY_SECONDS: float = Field(1.0, ge=0.0)
    LLM_RETRY_MAX_DELAY_SECONDS: float = Field(8.0, ge=0.0)

    # Debate failure tolerance
    DEBATE_MAX_SEAT_FAIL_RATIO: float = Field(0.4, ge=0.0, le=1.0)
    DEBATE_MIN_REQUIRED_SEATS: int = Field(1, ge=0)
    DEBATE_FAIL_FAST: bool = Field(True, description="Abort debates when too many seats fail.")

    # Provider health & circuit breaker (Patchset 28.0)
    PROVIDER_HEALTH_WINDOW_SECONDS: int = Field(300, description="Sliding window for health metrics (seconds)")
    PROVIDER_HEALTH_ERROR_THRESHOLD: float = Field(0.5, ge=0.0, le=1.0, description="Error rate threshold to open circuit")
    PROVIDER_HEALTH_MIN_CALLS: int = Field(10, ge=0, description="Minimum calls before circuit can open")
    PROVIDER_HEALTH_COOLDOWN_SECONDS: int = Field(60, ge=0, description="How long to keep circuit open (seconds)")

    # Celery queues (Patchset 28.0)
    DEBATE_DISPATCH_MODE: Literal["inline", "celery"] = "inline"
    DEBATE_FAST_QUEUE_NAME: str = "debates_fast"
    DEBATE_DEEP_QUEUE_NAME: str = "debates_deep"
    DEBATE_DEFAULT_QUEUE: str = "debates_fast"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    JWT_SECRET: str = "change_me_in_prod"
    JWT_EXPIRE_MINUTES: int = 1440
    JWT_TTL_SECONDS: int | None = None
    PASSWORD_ITERATIONS: int = 150000
    COOKIE_NAME: str = "consultaion_token"
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"
    COOKIE_PATH: str = "/"
    ENABLE_CSRF: bool = True
    CSRF_COOKIE_NAME: str = "csrf_token"

    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_WEBHOOK_VERIFY: bool = True
    STRIPE_WEBHOOK_INSECURE_DEV: bool = False
    BILLING_CHECKOUT_SUCCESS_URL: str | None = None
    BILLING_CHECKOUT_CANCEL_URL: str | None = None
    STRIPE_PRICE_PRO_ID: str | None = None
    BILLING_PROVIDER: str = "stripe"

    # Safety & security (Patchset 29.0)
    ENABLE_PII_SCRUB: bool = Field(True, description="Enable PII scrubbing before LLM calls")

    SENTRY_DSN: str | None = None
    SENTRY_ENV: str = "local"
    SENTRY_SAMPLE_RATE: float = 0.1

    WEB_CONCURRENCY: int | None = None
    GUNICORN_WORKERS: int | None = None

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URL: str | None = None
    GOOGLE_API_KEY: str | None = None

    OPENROUTER_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    AZURE_API_KEY: str | None = None
    LITELLM_API_KEY: str | None = None
    LITELLM_MODEL: str = "gpt-4o-mini"
    LITELLM_API_BASE: str | None = None

    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    FORCE_CREATE_ALL: bool = False

    RL_BACKOFF_ENABLED: bool = True
    N8N_WEBHOOK_URL: str | None = None

    EXPORT_DIR: str = "exports"

    def model_post_init(self, __context):
        # Patchset 29.0: Validate production secrets
        env_label = (self.ENV or "development").lower()
        local_envs = {"development", "dev", "local", "test"}
        is_local = env_label in local_envs
        object.__setattr__(self, "IS_LOCAL_ENV", is_local)
        if is_local:
            object.__setattr__(self, "COOKIE_SECURE", False)
        else:
            object.__setattr__(self, "ENABLE_SEC_HEADERS", True)
            object.__setattr__(self, "COOKIE_SECURE", True)
        
        # Production secret validation
        if not is_local:
            # JWT Secret
            if not self.JWT_SECRET or self.JWT_SECRET in ("change_me_in_prod", "CHANGE_ME_IN_PRODUCTION"):
                raise ValueError("JWT_SECRET must be set to a secure value in production (ENV={})".format(self.ENV))
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            
            # Stripe Webhook
            if self.STRIPE_WEBHOOK_VERIFY and not self.STRIPE_WEBHOOK_SECRET:
                raise ValueError("STRIPE_WEBHOOK_SECRET required when STRIPE_WEBHOOK_VERIFY=True in production")
            
            # LLM Providers
            if self.REQUIRE_REAL_LLM:
                has_provider = any([
                    self.OPENAI_API_KEY,
                    self.ANTHROPIC_API_KEY,
                    self.GEMINI_API_KEY,
                    self.GOOGLE_API_KEY,
                ])
                if not has_provider:
                    raise ValueError(
                        "At least one provider API key required when REQUIRE_REAL_LLM=1 in production. "\
                        "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY."
                    )
        else:
            # Local env: log warnings
            if not self.JWT_SECRET or self.JWT_SECRET in ("change_me_in_prod", "CHANGE_ME_IN_PRODUCTION"):
                logger.warning("JWT_SECRET not properly configured (OK for local env)")
            if self.STRIPE_WEBHOOK_VERIFY and not self.STRIPE_WEBHOOK_SECRET:
                logger.warning("STRIPE_WEBHOOK_VERIFY enabled but STRIPE_WEBHOOK_SECRET not set (OK for local env)")

        if self.RATE_LIMIT_BACKEND is None:
            object.__setattr__(
                self,
                "RATE_LIMIT_BACKEND",
                "redis" if self.REDIS_URL else "memory",
            )
        if not is_local:
            object.__setattr__(self, "RATE_LIMIT_BACKEND", "redis")
            if not self.REDIS_URL:
                raise RuntimeError("REDIS_URL is required when RATE_LIMIT_BACKEND=redis in non-dev environments")

        if self.JWT_TTL_SECONDS is None:
            object.__setattr__(self, "JWT_TTL_SECONDS", self.JWT_EXPIRE_MINUTES * 60)

        if not self.SSE_REDIS_URL and self.REDIS_URL:
            object.__setattr__(self, "SSE_REDIS_URL", self.REDIS_URL)
        if not is_local:
            # object.__setattr__(self, "SSE_BACKEND", "redis")  # Allow memory backend if workers=1
            if self.SSE_BACKEND == "redis" and not (self.SSE_REDIS_URL or self.REDIS_URL):
                raise RuntimeError("SSE_REDIS_URL or REDIS_URL is required for SSE in non-dev environments")

        broker = self.CELERY_BROKER_URL or self.SSE_REDIS_URL or self.REDIS_URL
        if broker:
            object.__setattr__(self, "CELERY_BROKER_URL", broker)
        backend = self.CELERY_RESULT_BACKEND or broker
        if backend:
            object.__setattr__(self, "CELERY_RESULT_BACKEND", backend)

        dispatch_mode = (self.DEBATE_DISPATCH_MODE or "inline").lower()
        if dispatch_mode not in {"inline", "celery"}:
            dispatch_mode = "inline"
        if dispatch_mode == "celery":
            if not self.CELERY_BROKER_URL:
                if is_local:
                    dispatch_mode = "inline"
                else:
                    raise RuntimeError("CELERY_BROKER_URL is required when DEBATE_DISPATCH_MODE=celery")
            elif not is_local and self.SSE_BACKEND.lower() != "redis":
                raise RuntimeError("SSE_BACKEND=redis is required when using Celery dispatch in non-dev environments")
        object.__setattr__(self, "DEBATE_DISPATCH_MODE", dispatch_mode)

        # SSE & Workers validation
        workers_count = int(self.WEB_CONCURRENCY or self.GUNICORN_WORKERS or 1)
        if workers_count > 1 and self.SSE_BACKEND.lower() != "redis":
            if not is_local:
                raise ValueError(
                    f"SSE_BACKEND='redis' is required when running with {workers_count} workers in production. "
                    "Configure REDIS_URL and set SSE_BACKEND=redis."
                )
            else:
                logger.warning(
                    f"Running with {workers_count} workers and SSE_BACKEND={self.SSE_BACKEND}. "
                    "SSE events may not be delivered correctly (OK for local dev)."
                )

        if self.VERCEL_URL and not self.VERCEL_URL.startswith("http"):
            object.__setattr__(self, "VERCEL_URL", f"https://{self.VERCEL_URL}")
        if self.NEXT_PUBLIC_VERCEL_URL and not self.NEXT_PUBLIC_VERCEL_URL.startswith("http"):
             object.__setattr__(self, "NEXT_PUBLIC_VERCEL_URL", f"https://{self.NEXT_PUBLIC_VERCEL_URL}")

        web_candidates = [
            self.WEB_APP_ORIGIN,
            self.VERCEL_URL,
            self.NEXT_PUBLIC_VERCEL_URL,
            self.NEXT_PUBLIC_WEB_URL,
            self.NEXT_PUBLIC_APP_URL,
            self.NEXT_PUBLIC_WEB_ORIGIN,
            self.NEXT_PUBLIC_APP_ORIGIN,
            self.NEXT_PUBLIC_SITE_URL,
        ]
        resolved = next((candidate for candidate in web_candidates if candidate), "http://localhost:3000")
        object.__setattr__(self, "WEB_APP_ORIGIN", resolved.rstrip("/"))


class SettingsProxy:
    def __init__(self) -> None:
        self._settings = AppSettings()

    def reload(self) -> None:
        previous_url = getattr(self._settings, "DATABASE_URL", None)
        self._settings = AppSettings()
        new_url = self._settings.DATABASE_URL
        
        if previous_url and new_url and previous_url != new_url:
            try:  # pragma: no cover - safeguards test envs that swap DB URLs
                from database import reset_engine

                reset_engine()
            except Exception:
                pass

    def __getattr__(self, name: str):  # pragma: no cover - passthrough
        return getattr(self._settings, name)


# Keep a process-wide singleton so tests that reload modules still share the same settings proxy.
_singleton = getattr(builtins, "_consultaion_settings_proxy", None)
if _singleton is None:
    _singleton = SettingsProxy()
    builtins._consultaion_settings_proxy = _singleton

settings = _singleton
