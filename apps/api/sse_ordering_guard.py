"""Cross-instance ordering guard for SSE publication.

Sequence allocation alone is not enough: two publishers can allocate N and N+1,
then publish N+1 before N. The client correctly discards an event older than its
observed high-water mark, so out-of-order delivery can permanently lose deltas.

This module wraps the existing backend publication primitive without changing
its envelope/history semantics:
- Redis: a short-lived per-channel distributed lock spans sequence allocation,
  history persistence, and Pub/Sub publish.
- Memory: a per-channel asyncio lock spans the same publication primitive.

The guard is installed by sse_terminal_contract, which is already imported on
the normal debate router startup path.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

_LOCK_TTL_MS = 30_000
_ACQUIRE_TIMEOUT_S = 10.0
_ACQUIRE_RETRY_S = 0.01

_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_installed = False
_original_redis_publish = None
_original_memory_publish = None


async def _acquire_redis_lock(client: Any, key: str) -> str:
    token = uuid.uuid4().hex
    deadline = time.monotonic() + _ACQUIRE_TIMEOUT_S
    while time.monotonic() < deadline:
        acquired = await client.set(key, token, nx=True, px=_LOCK_TTL_MS)
        if acquired:
            return token
        await asyncio.sleep(_ACQUIRE_RETRY_S)
    raise RuntimeError(f"Timed out acquiring SSE publication lock for {key}")


async def _release_redis_lock(client: Any, key: str, token: str) -> None:
    try:
        await client.eval(_RELEASE_SCRIPT, 1, key, token)
    except Exception:
        # TTL is the final safety net. Publication itself has already completed.
        pass


def _wrap_redis_publish(original):
    async def ordered(self, channel_id: str, event: dict):
        client = getattr(self, "_redis", None)
        if client is None:
            return await original(self, channel_id, event)
        lock_key = f"sse:publish:lock:{channel_id}"
        token = await _acquire_redis_lock(client, lock_key)
        try:
            return await original(self, channel_id, event)
        finally:
            await _release_redis_lock(client, lock_key, token)

    return ordered


def _wrap_memory_publish(original):
    async def ordered(self, channel_id: str, event: dict):
        locks = getattr(self, "_ordered_publish_locks", None)
        if locks is None:
            locks = {}
            self._ordered_publish_locks = locks
        lock = locks.get(channel_id)
        if lock is None:
            lock = asyncio.Lock()
            locks[channel_id] = lock
        async with lock:
            return await original(self, channel_id, event)

    return ordered


def install_sse_ordering_guard() -> None:
    global _installed, _original_redis_publish, _original_memory_publish
    if _installed:
        return

    from sse_backend import MemoryChannelBackend, RedisChannelBackend

    _original_redis_publish = RedisChannelBackend._publish_single
    _original_memory_publish = MemoryChannelBackend._publish_single

    RedisChannelBackend._publish_single = _wrap_redis_publish(_original_redis_publish)
    MemoryChannelBackend._publish_single = _wrap_memory_publish(_original_memory_publish)
    _installed = True
