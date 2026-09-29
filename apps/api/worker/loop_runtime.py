"""Run async work from Celery tasks without leaking loop-bound clients.

Each Celery task drives its coroutine with ``asyncio.run()``, which creates a
new event loop and closes it afterwards. The process-wide async Redis pool, the
SSE backend singleton (its background tasks and client) and the async database
pool all bind their connections to the loop that first used them. The next
task then ran on a new loop against connections of a closed one and failed
with ``RuntimeError: Event loop is closed``. Every other debate in a worker
process failed this way.

``run_task_coroutine`` releases those resources inside the loop, before it
closes, so the next task builds fresh ones on its own loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def release_loop_bound_resources() -> None:
    """Close clients bound to the running loop. Each step is best-effort."""
    try:
        from sse_backend import SSEBackendProvider

        provider = SSEBackendProvider._instance
        backend = getattr(provider, "_backend", None) if provider is not None else None
        if backend is not None:
            provider._backend = None
            stop = getattr(backend, "stop", None)
            if stop is not None:
                await stop()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("worker.loop_release.sse_failed: %s", exc)

    try:
        from redis_pool import close_async_redis

        await close_async_redis()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("worker.loop_release.redis_failed: %s", exc)

    try:
        import database_async

        await database_async.async_engine.dispose()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("worker.loop_release.db_failed: %s", exc)


def run_task_coroutine(factory: Callable[[], Awaitable[T]]) -> T:
    """``asyncio.run`` for Celery tasks, releasing loop-bound clients at the end."""

    async def _main() -> T:
        try:
            return await factory()
        finally:
            await release_loop_bound_resources()

    return asyncio.run(_main())
