from __future__ import annotations

from config import settings
from orchestrator import run_debate

try:
    from worker.debate_tasks import run_debate_task
except Exception:  # pragma: no cover - Celery optional in some envs
    run_debate_task = None  # type: ignore


async def dispatch_debate_run(
    debate_id: str,
    prompt: str,
    channel_id: str,
    config_data: dict,
    model_id: str | None,
) -> None:
    mode = (settings.DEBATE_DISPATCH_MODE or "inline").lower()
    if mode == "celery":
        if run_debate_task is None:
            raise RuntimeError("Celery dispatch selected but worker tasks are unavailable")
        run_debate_task.delay(debate_id)
        return

    await run_debate(
        debate_id,
        prompt,
        channel_id,
        config_data,
        model_id,
    )
