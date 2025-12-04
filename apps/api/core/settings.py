from pydantic import Field
from pydantic_settings import BaseSettings


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




class NotificationSettings(BaseSettings):
    enable_email_summaries: bool = Field(default=False, alias="ENABLE_EMAIL_SUMMARIES")
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")

    enable_slack_alerts: bool = Field(default=False, alias="ENABLE_SLACK_ALERTS")
    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class GiphySettings(BaseSettings):
    enable_giphy: bool = Field(default=False, alias="ENABLE_GIPHY")
    giphy_api_key: str | None = Field(default=None, alias="GIPHY_API_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class Settings(BaseSettings):
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    giphy: GiphySettings = Field(default_factory=GiphySettings)

settings = Settings()
