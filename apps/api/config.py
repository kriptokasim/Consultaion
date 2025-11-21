from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    ENV: str = "development"

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
    ENABLE_SEC_HEADERS: bool = True
    CORS_ORIGINS: str = "http://localhost:3000"
    WEB_APP_ORIGIN: str | None = None
    NEXT_PUBLIC_WEB_URL: str | None = None
    NEXT_PUBLIC_APP_URL: str | None = None
    NEXT_PUBLIC_WEB_ORIGIN: str | None = None
    NEXT_PUBLIC_APP_ORIGIN: str | None = None
    NEXT_PUBLIC_SITE_URL: str | None = None

    SSE_BACKEND: Literal["memory", "redis"] = "memory"
    SSE_REDIS_URL: str | None = None
    SSE_CHANNEL_TTL_SECONDS: int = 900

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
    BILLING_CHECKOUT_SUCCESS_URL: str | None = None
    BILLING_CHECKOUT_CANCEL_URL: str | None = None
    STRIPE_PRICE_PRO_ID: str | None = None
    BILLING_PROVIDER: str = "stripe"

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
        if self.RATE_LIMIT_BACKEND is None:
            object.__setattr__(
                self,
                "RATE_LIMIT_BACKEND",
                "redis" if self.REDIS_URL else "memory",
            )
        if self.JWT_TTL_SECONDS is None:
            object.__setattr__(self, "JWT_TTL_SECONDS", self.JWT_EXPIRE_MINUTES * 60)
        web_candidates = [
            self.WEB_APP_ORIGIN,
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
        self._settings = AppSettings()

    def __getattr__(self, name: str):  # pragma: no cover - passthrough
        return getattr(self._settings, name)


settings = SettingsProxy()
