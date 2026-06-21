from __future__ import annotations

import asyncio
import logging

from celery.utils.log import get_task_logger
from channels import debate_channel_id
from database import session_scope
from metrics import incr_metric
from models import Debate
from orchestrator import run_debate
from sse_backend import get_sse_backend

from worker.celery_app import celery_app

logger = get_task_logger(__name__)
module_logger = logging.getLogger(__name__)

_GIT_SHA = __import__("os").environ.get("GIT_SHA", "unknown")


async def _execute_debate_run(
    debate_id: str,
    trace_id: str | None = None,
    is_resume: bool = False,
    continuation_id: str | None = None,
) -> None:
    # Patchset 136: Log worker start with structured fields
    module_logger.info(
        "Worker starting debate execution",
        extra={
            "debate_id": debate_id,
            "trace_id": trace_id,
            "is_resume": is_resume,
            "git_sha": _GIT_SHA,
        },
    )
    incr_metric("debate.worker.started")

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            module_logger.warning("Debate %s not found for async execution", debate_id)
            incr_metric("debate.worker.failed")
            return
        prompt = debate.prompt
        config = debate.config or {}
        model_id = debate.model_id

    channel_id = debate_channel_id(debate_id)
    backend = get_sse_backend()
    await backend.create_channel(channel_id)
    try:
        await run_debate(
            debate_id,
            prompt,
            channel_id,
            config,
            model_id,
            trace_id=trace_id,
            is_resume=is_resume,
            continuation_id=continuation_id,
        )
        incr_metric("debate.worker.completed")
        module_logger.info(
            "Worker completed debate execution",
            extra={"debate_id": debate_id, "git_sha": _GIT_SHA},
        )
    except Exception:
        incr_metric("debate.worker.failed")
        raise


@celery_app.task(name="debates.run", bind=True, max_retries=3)
def run_debate_task(
    self,
    debate_id: str,
    trace_id: str | None = None,
    is_resume: bool = False,
    continuation_id: str | None = None,
) -> None:
    """Celery task that executes a debate orchestration by ID."""
    try:
        from observability.tracing import traced_span
        with traced_span("pipeline.run", {"debate_id": debate_id, "is_resume": str(is_resume)}):
            asyncio.run(
                _execute_debate_run(
                    debate_id,
                    trace_id=trace_id,
                    is_resume=is_resume,
                    continuation_id=continuation_id,
                )
            )
    except Exception as exc:  # pragma: no cover - Celery handles retries/logging
        logger.exception("Error while running debate %s", debate_id)
        raise self.retry(exc=exc, countdown=10) from exc
