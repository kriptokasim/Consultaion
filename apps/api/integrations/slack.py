from typing import Literal

import httpx
from loguru import logger

from config import settings

AlertLevel = Literal["info", "warning", "error"]


def is_slack_enabled() -> bool:
    return settings.ENABLE_SLACK_ALERTS and bool(settings.SLACK_WEBHOOK_URL)


def _complete_slack_transition(meta: dict | None) -> None:
    debate_id = str((meta or {}).get("debate_id") or "")
    if not debate_id:
        return
    try:
        from database import session_scope
        from services.terminal_transition import (
            TRANSITION_SLACK_ALERT,
            complete_transition_by_key,
        )

        with session_scope() as session:
            complete_transition_by_key(
                session,
                debate_id,
                TRANSITION_SLACK_ALERT,
            )
    except Exception:
        logger.warning(
            "Failed to complete Slack transition for debate %s",
            debate_id,
            exc_info=True,
        )


async def send_slack_alert(
    message: str,
    level: AlertLevel = "info",
    meta: dict | None = None,
    trace_id: str | None = None,
    mode: str | None = None,
) -> None:
    if not is_slack_enabled():
        return

    webhook_url = settings.SLACK_WEBHOOK_URL
    if not webhook_url:
        logger.warning("Slack alerts enabled but SLACK_WEBHOOK_URL missing; skipping.")
        return

    color = {
        "info": "#3B82F6",
        "warning": "#F59E0B",
        "error": "#EF4444",
    }[level]

    fields = [
        {"title": k, "value": str(v), "short": True}
        for k, v in (meta or {}).items()
    ]
    if trace_id:
        fields.append({"title": "Trace ID", "value": trace_id, "short": True})
    if mode:
        fields.append({"title": "Mode", "value": mode, "short": True})

    attachment = {
        "fallback": message,
        "color": color,
        "text": message,
        "fields": fields,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"attachments": [attachment]})
        resp.raise_for_status()
        _complete_slack_transition(meta)
        logger.info("Sent Slack alert: %s (%s)", message, level)
    except Exception as exc:
        # Leave terminal-transition claim reclaimable after its TTL.
        logger.warning("Failed to send Slack alert: %r", exc)
