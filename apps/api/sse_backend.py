from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Protocol

from config import settings

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - redis optional for memory backend
    redis = None


class BaseSSEBackend(Protocol):
    async def create_channel(self, channel_id: str) -> None:
        ...

    async def publish(self, channel_id: str, event: dict) -> None:
        ...

    async def subscribe(self, channel_id: str) -> AsyncIterator[dict]:
        ...

    async def cleanup(self) -> None:
        ...

    async def ping(self) -> bool:
        ...


class MemoryChannelBackend:
    def __init__(self, ttl_seconds: int = 900) -> None:
        self._ttl_seconds = ttl_seconds
        self._channels: dict[str, asyncio.Queue[dict]] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def create_channel(self, channel_id: str) -> None:
        async with self._lock:
            if channel_id not in self._channels:
                self._channels[channel_id] = asyncio.Queue()
            self._last_seen[channel_id] = time.time()

    async def publish(self, channel_id: str, event: dict) -> None:
        async with self._lock:
            queue = self._channels.get(channel_id)
            if not queue:
                queue = self._channels[channel_id] = asyncio.Queue()
            self._last_seen[channel_id] = time.time()
        await queue.put(event)

    async def subscribe(self, channel_id: str) -> AsyncIterator[dict]:
        await self.create_channel(channel_id)
        queue = self._channels[channel_id]
        while True:
            event = await queue.get()
            yield event

    async def cleanup(self) -> None:
        now = time.time()
        stale = [cid for cid, ts in self._last_seen.items() if now - ts > self._ttl_seconds]
        for cid in stale:
            self._channels.pop(cid, None)
            self._last_seen.pop(cid, None)

    async def ping(self) -> bool:
        return True


class RedisChannelBackend:
    def __init__(self, url: str, ttl_seconds: int = 900) -> None:
        if redis is None:
            raise RuntimeError("redis library is required for RedisChannelBackend")
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._redis = redis.from_url(url, encoding="utf-8", decode_responses=True)

    async def create_channel(self, channel_id: str) -> None:
        key = f"sse:meta:{channel_id}"
        await self._redis.set(key, "1", ex=self._ttl_seconds)

    async def publish(self, channel_id: str, event: dict) -> None:
        payload = json.dumps(event)
        await self._redis.publish(channel_id, payload)

    async def subscribe(self, channel_id: str) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel_id)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if not data:
                    continue
                yield json.loads(data)
        finally:
            await pubsub.unsubscribe(channel_id)
            await pubsub.close()

    async def cleanup(self) -> None:
        return None

    async def ping(self) -> bool:
        return bool(await self._redis.ping())


_sse_backend: BaseSSEBackend | None = None


def get_sse_backend() -> BaseSSEBackend:
    global _sse_backend
    if _sse_backend is not None:
        return _sse_backend

    if settings.SSE_BACKEND.lower() == "redis":
        url = settings.SSE_REDIS_URL or settings.REDIS_URL
        # Validate Redis URL format before attempting to use it
        if url and url.strip() and (url.startswith("redis://") or url.startswith("rediss://") or url.startswith("unix://")):
            _sse_backend = RedisChannelBackend(url=url, ttl_seconds=settings.SSE_CHANNEL_TTL_SECONDS)
        else:
            # Fall back to memory if Redis URL is missing or invalid
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "SSE_BACKEND=redis but REDIS_URL is invalid or missing (%s). Falling back to memory backend.",
                url or "<not set>"
            )
            _sse_backend = MemoryChannelBackend(ttl_seconds=settings.SSE_CHANNEL_TTL_SECONDS)
    else:
        _sse_backend = MemoryChannelBackend(ttl_seconds=settings.SSE_CHANNEL_TTL_SECONDS)

    return _sse_backend


def reset_sse_backend_for_tests() -> None:
    global _sse_backend
    _sse_backend = None
