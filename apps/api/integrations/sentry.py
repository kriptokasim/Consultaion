import logging
import sentry_sdk
from config import settings
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

logger = logging.getLogger(__name__)

def init_sentry() -> None:
    """Canonical Sentry initialization for the application."""
    if not settings.SENTRY_DSN or not settings.SENTRY_DSN.strip().startswith("http"):
        logger.info("Sentry DSN not configured or invalid. Skipping Sentry initialization.")
        return

    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENV,
            traces_sample_rate=float(settings.SENTRY_SAMPLE_RATE),
            # Send PII only if explicitly desired or if you have data scrubbing rules
            send_default_pii=True,
            enable_logs=True,
            profile_session_sample_rate=1.0,  # Or configure via settings if desired
            profile_lifecycle="trace",
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        )
        logger.info("Sentry initialized successfully [deduplicated]")
    except Exception as e:
        logger.warning("Failed to initialize Sentry: %s. Continuing without Sentry.", e)
