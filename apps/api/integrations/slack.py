from typing import Literal

import httpx
from core.settings import settings
from loguru import logger

AlertLevel = Literal["info", "warning", "error"]

def is_slack_enabled() -> bool:
    cfg = settings.notifications
    return cfg.enable_slack_alerts and bool(cfg.slack_webhook_url)

async def send_slack_alert(
    message: str,
    level: AlertLevel = "info",
    meta: dict | None = None,
) -> None:
    if not is_slack_enabled():
        return

    webhook_url = settings.notifications.slack_webhook_url
    if not webhook_url:
        logger.warning("Slack alerts enabled but SLACK_WEBHOOK_URL missing; skipping.")
        return

    color = {
        "info": "#3B82F6",   # blue
        "warning": "#F59E0B",# amber
        "error": "#EF4444",  # red
    }[level]

    attachment = {
        "fallback": message,
        "color": color,
        "text": message,
        "fields": [
            {"title": k, "value": str(v), "short": True}
            for k, v in (meta or {}).items()
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"attachments": [attachment]})
        resp.raise_for_status()
        logger.info("Sent Slack alert: %s (%s)", message, level)
    except Exception as exc:
        logger.warning("Failed to send Slack alert: %r", exc)
