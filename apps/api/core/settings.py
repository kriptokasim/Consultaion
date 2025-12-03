from pydantic_settings import BaseSettings
from functools import lru_cache

class ObservabilitySettings(BaseSettings):
    enable_langfuse: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    enable_posthog: bool = False
    posthog_api_key: str | None = None
    posthog_host: str | None = None

    class Config:
        env_prefix = ""  # read directly from LANGFUSE_*/POSTHOG_*
        case_sensitive = False
        extra = "ignore"

@lru_cache()
def get_observability_settings() -> ObservabilitySettings:
    return ObservabilitySettings()  # type: ignore[call-arg]
