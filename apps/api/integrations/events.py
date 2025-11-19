from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


def emit_event(event: str, payload: Dict[str, Any]) -> None:
    """Send a lightweight event to n8n or other automation pipeline."""
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        httpx.post(webhook_url, json={"event": event, "payload": payload}, timeout=2)
    except Exception:
        logger.warning("Failed to emit n8n event %s", event, exc_info=True)
