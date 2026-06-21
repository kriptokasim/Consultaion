from __future__ import annotations

import logging

from config import settings
from orchestrator import run_debate

try:
    from worker.debate_tasks import run_debate_task
except Exception:  # pragma: no cover - Celery optional in some envs
    run_debate_task = None  # type: ignore

logger = logging.getLogger(__name__)


def choose_queue_for_debate(config_data: dict | None, settings_obj=settings) -> str:
    """
    Select an appropriate Celery queue for a debate configuration.

    Uses a light heuristic on the config's mode; falls back to the default queue.
    """
    mode = None
    if isinstance(config_data, dict):
        mode_value = config_data.get("mode")
        mode = mode_value.lower() if isinstance(mode_value, str) else None

    if mode == "fast":
        return settings_obj.DEBATE_FAST_QUEUE_NAME
    if mode == "deep":
        return settings_obj.DEBATE_DEEP_QUEUE_NAME
    return settings_obj.DEBATE_DEFAULT_QUEUE


async def dispatch_debate_run(
    debate_id: str,
    prompt: str,
    channel_id: str,
    config_data: dict,
    model_id: str | None,
    trace_id: str | None = None,
    resume: bool = False,
    continuation_id: str | None = None,
) -> None:
    # Propagate correlation context into background task
    from correlation import create_child_context, get_correlation_context
    ctx = get_correlation_context()
    if ctx:
        ctx = create_child_context(debate_id=debate_id)

    mode = (settings.DEBATE_DISPATCH_MODE or "inline").lower()

    # Patchset 136: Structured dispatch logging
    dispatch_meta = {
        "debate_id": debate_id,
        "dispatch_mode": mode,
        "model_id": model_id,
        "trace_id": trace_id,
        "resume": resume,
    }

    if mode == "celery":
        if run_debate_task is None:
            from metrics import incr_metric
            incr_metric("debate.dispatch.celery_schedule_failed")
            logger.error(
                "Celery dispatch selected but worker tasks unavailable",
                extra=dispatch_meta,
            )
            raise RuntimeError("Celery dispatch selected but worker tasks are unavailable")
        queue_name = choose_queue_for_debate(config_data, settings)
        dispatch_meta["queue"] = queue_name
        try:
            if hasattr(run_debate_task, "apply_async"):
                run_debate_task.apply_async(args=[debate_id, trace_id], kwargs={"is_resume": resume, "continuation_id": continuation_id}, queue=queue_name)
            else:  # pragma: no cover - fall back for unusual task shims
                run_debate_task.delay(debate_id, trace_id, is_resume=resume, continuation_id=continuation_id)
            from metrics import incr_metric
            incr_metric("debate.dispatch.celery_scheduled")
            logger.info("Dispatched debate via Celery", extra=dispatch_meta)
        except Exception as exc:
            from metrics import incr_metric
            incr_metric("debate.dispatch.celery_schedule_failed")
            logger.error("Failed to schedule Celery task", extra={**dispatch_meta, "error": str(exc)})
            raise
        return

    from metrics import incr_metric
    incr_metric("debate.dispatch.inline_started")
    logger.info("Dispatching debate inline", extra=dispatch_meta)

    from observability.tracing import traced_span
    with traced_span("debate.run", {"debate_id": debate_id, "resume": str(resume)}):
        await run_debate(
            debate_id,
            prompt,
            channel_id,
            config_data,
            model_id,
            trace_id=trace_id,
            is_resume=resume,
            continuation_id=continuation_id,
        )

