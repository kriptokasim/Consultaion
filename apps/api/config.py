from __future__ import annotations

import os


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./consultaion.db")
    REDIS_URL: str | None = os.getenv("REDIS_URL")

    SSE_BACKEND: str = os.getenv("SSE_BACKEND", "memory")
    SSE_REDIS_URL: str | None = os.getenv("SSE_REDIS_URL")
    SSE_CHANNEL_TTL_SECONDS: int = int(os.getenv("SSE_CHANNEL_TTL_SECONDS", "900"))

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
