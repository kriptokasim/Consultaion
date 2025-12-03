from __future__ import annotations

from config import settings
from orchestrator import run_debate

try:
    from worker.debate_tasks import run_debate_task
except Exception:  # pragma: no cover - Celery optional in some envs
    run_debate_task = None  # type: ignore


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
) -> None:
    mode = (settings.DEBATE_DISPATCH_MODE or "inline").lower()
    if mode == "celery":
        if run_debate_task is None:
            raise RuntimeError("Celery dispatch selected but worker tasks are unavailable")
        queue_name = choose_queue_for_debate(config_data, settings)
        if hasattr(run_debate_task, "apply_async"):
            # Pass trace_id to the task
            run_debate_task.apply_async(args=[debate_id, trace_id], queue=queue_name)
        else:  # pragma: no cover - fall back for unusual task shims
            run_debate_task.delay(debate_id, trace_id)
        return

    await run_debate(
        debate_id,
        prompt,
        channel_id,
        config_data,
        model_id,
        trace_id=trace_id,
    )
