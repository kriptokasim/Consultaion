from __future__ import annotations

import asyncio
import logging

from celery.utils.log import get_task_logger
from channels import debate_channel_id
from database import session_scope
from models import Debate
from orchestrator import run_debate
from sse_backend import get_sse_backend

from worker.celery_app import celery_app

logger = get_task_logger(__name__)
module_logger = logging.getLogger(__name__)


async def _execute_debate_run(debate_id: str) -> None:
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            module_logger.warning("Debate %s not found for async execution", debate_id)
            return
        prompt = debate.prompt
        config = debate.config or {}
        model_id = debate.model_id

    channel_id = debate_channel_id(debate_id)
    backend = get_sse_backend()
    await backend.create_channel(channel_id)
    await run_debate(debate_id, prompt, channel_id, config, model_id)


@celery_app.task(name="debates.run", bind=True, max_retries=3)
def run_debate_task(self, debate_id: str) -> None:
    """Celery task that executes a debate orchestration by ID."""
    try:
        asyncio.run(_execute_debate_run(debate_id))
    except Exception as exc:  # pragma: no cover - Celery handles retries/logging
        logger.exception("Error while running debate %s", debate_id)
        raise self.retry(exc=exc, countdown=10) from exc
