from __future__ import annotations

from typing import Any, Optional

from core.settings import settings
from loguru import logger

_posthog_client: Optional[Any] = None  # type: ignore[assignment]


def get_posthog():
  # lazy import to avoid dependency if unused
  global _posthog_client
  if _posthog_client is not None:
      return _posthog_client

  obs_settings = settings.observability
  if not obs_settings.enable_posthog or not obs_settings.posthog_api_key:
      return None

  try:
      from posthog import Posthog  # type: ignore[import]
      _posthog_client = Posthog(api_key=obs_settings.posthog_api_key, host=obs_settings.posthog_host)
  except Exception as exc:  # pragma: no cover - defensive
      logger.exception("Failed to init PostHog client: {}", exc)
      _posthog_client = None

  return _posthog_client


def track_event(event: str, distinct_id: str, properties: dict[str, Any] | None = None) -> None:
    client = get_posthog()
    if client is None:
        return

    try:
        client.capture(distinct_id=distinct_id, event=event, properties=properties or {})
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to send PostHog event {}: {}", event, exc)
