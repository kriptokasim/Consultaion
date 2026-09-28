"""Celery tasks must not reuse clients bound to a previous task's event loop."""

import asyncio
from unittest.mock import AsyncMock, patch

from worker.loop_runtime import run_task_coroutine


class _LoopBoundBackend:
    """Stands in for the SSE backend: usable only on the loop that created it."""

    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.stopped = False

    async def publish(self, channel_id, event):
        if asyncio.get_running_loop() is not self.loop or self.loop.is_closed():
            raise RuntimeError("Event loop is closed")

    async def stop(self):
        self.stopped = True


def test_consecutive_tasks_get_clients_for_their_own_loop():
    from sse_backend import SSEBackendProvider

    created: list[_LoopBoundBackend] = []

    def _create():
        backend = _LoopBoundBackend()
        created.append(backend)
        return backend

    async def task_body():
        from sse_backend import get_sse_backend

        await get_sse_backend().publish("debate:x", {"type": "notice"})

    SSEBackendProvider.reset_instance_for_tests()
    try:
        with (
            patch("sse_backend.create_sse_backend", side_effect=_create),
            patch("redis_pool.close_async_redis", new_callable=AsyncMock) as close_redis,
        ):
            # Without the release, the second task published through the first
            # loop's backend and failed with "Event loop is closed".
            run_task_coroutine(task_body)
            run_task_coroutine(task_body)
    finally:
        SSEBackendProvider.reset_instance_for_tests()

    assert len(created) == 2
    assert created[0] is not created[1]
    assert all(backend.stopped for backend in created)
    assert close_redis.await_count == 2


def test_resources_are_released_even_when_the_task_fails():
    import pytest

    async def failing():
        raise ValueError("boom")

    with patch("worker.loop_runtime.release_loop_bound_resources", new_callable=AsyncMock) as release:
        with pytest.raises(ValueError):
            run_task_coroutine(failing)
    release.assert_awaited_once()
