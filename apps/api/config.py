from __future__ import annotations

import builtins
import logging
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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
    
    # Standardized environment detection (derived from ENV)
    # Values: "local", "staging", "production"
    APP_ENV: str = "local"

    DATABASE_URL: str = "sqlite:///./consultaion.db"
    DATABASE_URL_ASYNC: str | None = None
    REDIS_URL: str | None = None
    
    # LLM Provider Timeouts
    LLM_TIMEOUT_SECONDS: int = 30  # Timeout for individual model calls
    LLM_MAX_RETRIES: int = 1  # Max retries on transient failures
    
    # Patchset 58.0: Data retention settings (days, None = indefinite)
    # These are configuration knobs, not final legal obligations
    RETAIN_DEBATES_DAYS: int = 365
    RETAIN_DEBATE_ERRORS_DAYS: int = 90
    RETAIN_SUPPORT_NOTES_DAYS: int | None = None  # Indefinite by default
    RETAIN_USAGE_STATS_DAYS: int = 365

    # Owner override (Patchset 103)
    OWNER_EMAIL_ALLOWLIST: str = ""   # comma-separated emails
    OWNER_PLAN: str = "pro"
    OWNER_UNLIMITED: bool = False

    @property
    def owner_emails(self) -> list[str]:
        """Parse comma-separated allowlist into normalized email list."""
        if not self.OWNER_EMAIL_ALLOWLIST:
            return []
        return [e.strip().lower() for e in self.OWNER_EMAIL_ALLOWLIST.split(",") if e.strip()]

    RATE_LIMIT_BACKEND: Literal["redis", "memory"] | None = None
    
    # Production Rate Limits (stricter for public users)
    PROD_RL_WINDOW: int = 60
    PROD_RL_MAX_CALLS: int = 60
    PROD_RL_DEBATE_CREATE_WINDOW: int = 60
    PROD_RL_DEBATE_CREATE_MAX_CALLS: int = 10
    PROD_AUTH_RL_WINDOW: int = 300
    PROD_AUTH_RL_MAX_CALLS: int = 100  # Increased for troubleshooting
    
    # Development Rate Limits (relaxed for testing)
    DEV_RL_WINDOW: int = 60
    DEV_RL_MAX_CALLS: int = 300  # Much higher for development
    DEV_RL_DEBATE_CREATE_WINDOW: int = 60
    DEV_RL_DEBATE_CREATE_MAX_CALLS: int = 50  # Relaxed for testing
    DEV_AUTH_RL_WINDOW: int = 300
    DEV_AUTH_RL_MAX_CALLS: int = 50
    
    # Active rate limits (set based on ENV in model_post_init)
    RL_WINDOW: int = 60
    RL_MAX_CALLS: int = 60
    RL_DEBATE_CREATE_WINDOW: int = 60
    RL_DEBATE_CREATE_MAX_CALLS: int = 10
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
    ENABLE_CONVERSATION_MODE: bool = Field(False, description="Enable new conversation mode")
    ENABLE_GIPHY: bool = Field(False, description="Enable Giphy integration visual delights")
    ENABLE_EMAIL_SUMMARIES: bool = Field(False, description="Enable email summary notifications")
    ENABLE_SLACK_ALERTS: bool = Field(False, description="Enable Slack webhook alerts")
    
    # Patchset 76: Enhanced conversation UX with delayed voting
    ENABLE_CONVERSATION_V2: bool = Field(False, description="Enable enhanced conversation UX with delayed voting and structured vote reasons")
    
    # Patchset 50.3: Beta Access Control
    ENABLE_BETA_ACCESS: bool = Field(False, description="Enable beta access restrictions")
    BETA_WHITELIST: str = Field("", description="Comma-separated list of beta user emails")
    
    # Conversation Mode Limits
    CONVERSATION_MAX_ROUNDS: int = Field(4, ge=1, description="Maximum number of conversation rounds")
    CONVERSATION_MAX_TOKENS_PER_ROUND: int = Field(2048, ge=100, description="Max tokens per round")
    CONVERSATION_MAX_TOTAL_TOKENS: int = Field(8000, ge=1000, description="Max total tokens for conversation")

    APP_VERSION: str = "0.2.0"

    LOG_LEVEL: str = "INFO"
    
    # Sentry Configuration
    SENTRY_DSN: str | None = Field(
        "https://ddf2ec99d4dc9d15066c4e4927534818@o4510567771406336.ingest.de.sentry.io/4510567774027856",
        description="Sentry DSN for error tracking"
    )

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
    SSE_POLL_TIMEOUT_SECONDS: float = 1.0  # Patchset 67.0: Poll timeout for memory backend subscribe
    
    # Patchset 75: SSE strict mode and memory backend limits
    SSE_REDIS_STRICT: bool | None = None  # None = auto (strict in prod, lenient in local)
    SSE_MEMORY_MAX_QUEUE_SIZE: int = 1000
    SSE_MEMORY_IDLE_TIMEOUT_SECONDS: int = 3600  # 1 hour max idle time for subscriptions

    # LLM retry controls
    LLM_RETRY_ENABLED: bool = Field(True, description="Enable retry/backoff around LLM calls.")
    LLM_RETRY_MAX_ATTEMPTS: int = Field(3, ge=1, le=10)
    LLM_RETRY_INITIAL_DELAY_SECONDS: float = Field(1.0, ge=0.0)
    LLM_RETRY_MAX_DELAY_SECONDS: float = Field(8.0, ge=0.0)

    # Debate failure tolerance
    DEBATE_MAX_SEAT_FAIL_RATIO: float = Field(0.4, ge=0.0, le=1.0)
    DEBATE_MIN_REQUIRED_SEATS: int = Field(1, ge=0)
    DEBATE_FAIL_FAST: bool = Field(True, description="Abort debates when too many seats fail.")

    # Patchset 66.0: Stale debate cleanup settings
    DEBATE_STALE_RUNNING_SECONDS: int = Field(3600, description="Max seconds a debate can stay 'running' before cleanup")
    DEBATE_STALE_QUEUED_SECONDS: int = Field(1800, description="Max seconds a debate can stay 'queued' before cleanup")
    DEBATE_CLEANUP_LOOP_SECONDS: int = Field(60, description="Interval between cleanup loop iterations")
    DEBATE_RESUME_TOKEN_TTL_SECONDS: int = Field(300, description="TTL for resume token ownership claims")

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

    # Patchset 53.0: Auth Debug Mode
    AUTH_DEBUG: bool = Field(False, description="Enable verbose auth logging & debug endpoint")

    JWT_SECRET: str = "change_me_in_prod"
    JWT_EXPIRE_MINUTES: int = 1440
    JWT_TTL_SECONDS: int | None = None
    PASSWORD_ITERATIONS: int = 150000
    COOKIE_NAME: str = "consultaion_token"
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"
    COOKIE_PATH: str = "/"
    COOKIE_DOMAIN: str | None = None
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
    
    # Langfuse Observability (Patchset v2.0)
    ENABLE_LANGFUSE: bool = Field(default=False, description="Enable Langfuse tracing")
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    WEB_CONCURRENCY: int | None = None
    GUNICORN_WORKERS: int | None = None

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URL: str | None = None
    GOOGLE_API_KEY: str | None = None

    OPENROUTER_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    MISTRAL_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    AZURE_API_KEY: str | None = None
    LITELLM_API_KEY: str | None = None
    LITELLM_MODEL: str = "gpt-4o-mini"
    LITELLM_API_BASE: str | None = None
    OPENROUTER_FALLBACK_MODEL: str = "openrouter/openai/gpt-4o-mini"

    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_TIMEOUT: int = 30
    FORCE_CREATE_ALL: bool = False

    RL_BACKOFF_ENABLED: bool = True
    N8N_WEBHOOK_URL: str | None = None

    EXPORT_DIR: str = "exports"

    @field_validator("WEB_CONCURRENCY", "GUNICORN_WORKERS", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for optional integer fields."""
        if v == "":
            return None
        return v

    def model_post_init(self, __context):
        # Patchset 29.0: Validate production secrets
        env_label = (self.ENV or "development").lower()
        local_envs = {"development", "dev", "local", "test"}
        
        
        # Patchset 51.0: Auto-detect Render environment
        # Render sets 'RENDER' env var (value can be "true", "True", "1", etc.)
        render_var = os.environ.get("RENDER", "").lower()
        is_render = render_var in ("true", "1", "yes")
        
        is_local = env_label in local_envs and not is_render
        object.__setattr__(self, "IS_LOCAL_ENV", is_local)
        
        # Patchset 54.0: Standardize APP_ENV for telemetry and feature gating
        if is_local:
            app_env = "local"
        elif env_label in ("staging", "stage"):
            app_env = "staging"
        else:
            # Production or unknown -> treat as production
            app_env = "production"
        object.__setattr__(self, "APP_ENV", app_env)
        
        # Set active rate limits based on environment
        if is_local:
            object.__setattr__(self, "RL_WINDOW", self.DEV_RL_WINDOW)
            object.__setattr__(self, "RL_MAX_CALLS", self.DEV_RL_MAX_CALLS)
            object.__setattr__(self, "RL_DEBATE_CREATE_WINDOW", self.DEV_RL_DEBATE_CREATE_WINDOW)
            object.__setattr__(self, "RL_DEBATE_CREATE_MAX_CALLS", self.DEV_RL_DEBATE_CREATE_MAX_CALLS)
            object.__setattr__(self, "AUTH_RL_WINDOW", self.DEV_AUTH_RL_WINDOW)
            object.__setattr__(self, "AUTH_RL_MAX_CALLS", self.DEV_AUTH_RL_MAX_CALLS)
        else:
            object.__setattr__(self, "RL_WINDOW", self.PROD_RL_WINDOW)
            object.__setattr__(self, "RL_MAX_CALLS", self.PROD_RL_MAX_CALLS)
            object.__setattr__(self, "RL_DEBATE_CREATE_WINDOW", self.PROD_RL_DEBATE_CREATE_WINDOW)
            object.__setattr__(self, "RL_DEBATE_CREATE_MAX_CALLS", self.PROD_RL_DEBATE_CREATE_MAX_CALLS)
            object.__setattr__(self, "AUTH_RL_WINDOW", self.PROD_AUTH_RL_WINDOW)
            object.__setattr__(self, "AUTH_RL_MAX_CALLS", self.PROD_AUTH_RL_MAX_CALLS)
        
        if is_local:
            object.__setattr__(self, "COOKIE_SECURE", False)
        else:
            object.__setattr__(self, "ENABLE_SEC_HEADERS", True)
            object.__setattr__(self, "COOKIE_SECURE", True)
            object.__setattr__(self, "COOKIE_SAMESITE", "none")
            # Auto-derive COOKIE_DOMAIN from WEB_APP_ORIGIN for cross-subdomain cookies
            # Auto-derive COOKIE_DOMAIN from WEB_APP_ORIGIN for cross-subdomain cookies
            if not self.COOKIE_DOMAIN:
                from urllib.parse import urlparse
                parsed = urlparse(self.WEB_APP_ORIGIN or "")
                host = parsed.hostname or ""
                parts = host.split(".")
                # Patchset 105: Ensure we capture the root domain for subdomains
                # e.g., web.consultaion.com -> .consultaion.com
                if len(parts) >= 2:
                    # Logic: if >= 2 parts, use last two (e.g. consultaion.com) prefixed with dot
                    # This works for .com, .net, etc. Be careful with .co.uk if needed, but for now simple 2-part
                    self.COOKIE_DOMAIN = "." + ".".join(parts[-2:])
                else:
                    # Localhost or single name
                    self.COOKIE_DOMAIN = None
        
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
                    self.OPENROUTER_API_KEY,
                    self.GROQ_API_KEY,
                    self.MISTRAL_API_KEY,
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

        # Patchset 72: Async DB URL
        if not self.DATABASE_URL_ASYNC:
            url = self.DATABASE_URL
            async_url = url
            if url.startswith("sqlite"):
                async_url = url.replace("sqlite:", "sqlite+aiosqlite:")
            elif url.startswith("postgres"):
                async_url = url.replace("postgresql:", "postgresql+psycopg:").replace("postgres:", "postgresql+psycopg:")
            object.__setattr__(self, "DATABASE_URL_ASYNC", async_url)

        if not self.SSE_REDIS_URL and self.REDIS_URL:
            object.__setattr__(self, "SSE_REDIS_URL", self.REDIS_URL)
        if not is_local:
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

        # If running on Vercel (VERCEL_URL is set), ignore localhost WEB_APP_ORIGIN
        # This prevents local .env or default values from overriding the Vercel URL
        if self.VERCEL_URL and self.WEB_APP_ORIGIN and "localhost" in self.WEB_APP_ORIGIN:
             object.__setattr__(self, "WEB_APP_ORIGIN", None)

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

        # Ensure CORS_ORIGINS includes the resolved WEB_APP_ORIGIN
        # This is critical for cross-domain authentication to work
        cors_origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if resolved not in cors_origins:
            cors_origins.append(resolved)
        object.__setattr__(self, "CORS_ORIGINS", ",".join(cors_origins))
        
        # Patchset 73: Strict CORS Validation
        if not is_local:
             if "*" in cors_origins:
                 raise ValueError("Wildcard CORS origin '*' is not allowed in production. Set explicit CORS_ORIGINS.")
             if not cors_origins:
                 raise ValueError("CORS_ORIGINS must be set in production.")


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
