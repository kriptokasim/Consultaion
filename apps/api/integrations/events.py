from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict

import httpx

from config import settings

logger = logging.getLogger(__name__)


async def _send_event_async(webhook_url: str, event: str, payload: Dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=2) as client:
        await client.post(webhook_url, json={"event": event, "payload": payload})


def emit_event(event: str, payload: Dict[str, Any]) -> None:
    """Send a lightweight event to n8n or other automation pipeline without blocking requests."""
    webhook_url = settings.N8N_WEBHOOK_URL
    if not webhook_url:
        return

    async def _runner() -> None:
        try:
            await _send_event_async(webhook_url, event, payload)
        except Exception:
            logger.warning("Failed to emit n8n event %s", event, exc_info=True)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        threading.Thread(target=lambda: asyncio.run(_runner()), daemon=True).start()
    else:
        loop.create_task(_runner())
