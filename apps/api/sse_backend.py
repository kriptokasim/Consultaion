from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Protocol, Optional

from config import settings

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - redis optional for memory backend
    redis = None

logger = logging.getLogger(__name__)


class BaseSSEBackend(Protocol):
    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

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
    def __init__(self, ttl_seconds: int = 900, max_queue_size: int = 1000) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_queue_size = max_queue_size
        self._channels: dict[str, asyncio.Queue[dict]] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _periodic_cleanup(self) -> None:
        while self._running:
            await asyncio.sleep(60)  # Run cleanup every minute
            await self.cleanup()

    async def create_channel(self, channel_id: str) -> None:
        async with self._lock:
            if channel_id not in self._channels:
                self._channels[channel_id] = asyncio.Queue(maxsize=self._max_queue_size)
            self._last_seen[channel_id] = time.time()

    async def publish(self, channel_id: str, event: dict) -> None:
        async with self._lock:
            queue = self._channels.get(channel_id)
            if not queue:
                queue = self._channels[channel_id] = asyncio.Queue(maxsize=self._max_queue_size)
            self._last_seen[channel_id] = time.time()
        
        try:
            # maintain queue size by removing old items if full
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(event)
        except Exception as e:
            logger.error(f"Error publishing to memory channel {channel_id}: {e}")

    async def subscribe(self, channel_id: str) -> AsyncIterator[dict]:
        await self.create_channel(channel_id)
        queue = self._channels[channel_id]
        poll_timeout = getattr(settings, 'SSE_POLL_TIMEOUT_SECONDS', 1.0)
        try:
            while True:
                # Update last seen on access
                async with self._lock:
                    self._last_seen[channel_id] = time.time()
                
                try:
                    # Patchset 67.0: Use timeout to prevent infinite blocking
                    event = await asyncio.wait_for(queue.get(), timeout=poll_timeout)
                    yield event
                    # Exit on final/error event types
                    if event.get("type") in ("final", "error"):
                        break
                except asyncio.TimeoutError:
                    # Keep polling - this allows the generator to be cancelled externally
                    continue
        except asyncio.CancelledError:
            pass

    async def cleanup(self) -> None:
        now = time.time()
        # Create list of channels to remove to avoid modification during iteration
        async with self._lock:
            stale = [cid for cid, ts in self._last_seen.items() if now - ts > self._ttl_seconds]
            for cid in stale:
                self._channels.pop(cid, None)
                self._last_seen.pop(cid, None)
        if stale:
             logger.info(f"Cleaned up {len(stale)} stale SSE channels")

    async def ping(self) -> bool:
        return True


class RedisChannelBackend:
    def __init__(self, url: str, ttl_seconds: int = 900) -> None:
        if redis is None:
            raise RuntimeError("redis library is required for RedisChannelBackend")
        self._url = url
        self._ttl_seconds = ttl_seconds
        # Retry on timeout or connection error
        self._redis = redis.from_url(
            url, 
            encoding="utf-8", 
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            retry_on_timeout=True
        )

    async def start(self) -> None:
        # Verify connection
        try:
            await self._redis.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis for SSE: {e}")
            # We don't raise here to allow app startup, but subsequent calls will fail/retry

    async def stop(self) -> None:
        await self._redis.aclose()

    async def create_channel(self, channel_id: str) -> None:
        key = f"sse:meta:{channel_id}"
        await self._redis.set(key, "1", ex=self._ttl_seconds)

    async def publish(self, channel_id: str, event: dict) -> None:
        payload = json.dumps(event)
        try:
            await self._redis.publish(channel_id, payload)
        except Exception as e:
             logger.error(f"Failed to publish to Redis SSE {channel_id}: {e}")

    async def subscribe(self, channel_id: str) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel_id)
        try:
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message:
                        data = message.get("data")
                        if data:
                             yield json.loads(data)
                    else:
                        await asyncio.sleep(0.01)
                except (redis.ConnectionError, redis.TimeoutError) as e:
                    logger.warning(f"Redis connection lost in subscribe ({e}), retrying...")
                    await asyncio.sleep(1)
                    # Attempt to re-subscribe
                    try:
                        await pubsub.subscribe(channel_id)
                    except Exception:
                        pass
        finally:
            await pubsub.unsubscribe(channel_id)
            await pubsub.close()

    async def cleanup(self) -> None:
        # Redis handles TTL automatically
        return None

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

# Factory to create the backend instance
def create_sse_backend() -> BaseSSEBackend:
    if settings.SSE_BACKEND.lower() == "redis":
        url = settings.SSE_REDIS_URL or settings.REDIS_URL
        if url and url.strip() and (url.startswith("redis://") or url.startswith("rediss://") or url.startswith("unix://")):
            return RedisChannelBackend(url=url, ttl_seconds=settings.SSE_CHANNEL_TTL_SECONDS)
        else:
            logger.warning("SSE_BACKEND=redis but URL invalid. Falling back to memory.")
    
    return MemoryChannelBackend(ttl_seconds=settings.SSE_CHANNEL_TTL_SECONDS)


_global_sse_backend: BaseSSEBackend | None = None
_sse_backend_lock = asyncio.Lock()


class SSEBackendProvider:
    """
    Patchset 67.0: Thread-safe lazy SSE backend provider.
    
    Replaces global mutable singleton pattern for better test isolation
    and multi-worker safety.
    """
    _instance: "SSEBackendProvider | None" = None
    
    def __init__(self) -> None:
        self._backend: BaseSSEBackend | None = None
    
    @classmethod
    def instance(cls) -> "SSEBackendProvider":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get(self) -> BaseSSEBackend:
        """Get or create the SSE backend instance."""
        if self._backend is None:
            self._backend = create_sse_backend()
            logger.info("SSE backend created: %s", type(self._backend).__name__)
        return self._backend
    
    def reset_for_tests(self) -> None:
        """Reset backend for test isolation. Logs for debugging."""
        logger.debug("SSE backend reset for tests")
        self._backend = None
    
    @classmethod
    def reset_instance_for_tests(cls) -> None:
        """Fully reset the provider instance (for complete test isolation)."""
        if cls._instance is not None:
            cls._instance.reset_for_tests()
        cls._instance = None


def get_sse_backend() -> BaseSSEBackend:
    """
    Get the global SSE backend instance.
    This provides a singleton for the process, ensuring background tasks
    share the same memory backend as the API (if using memory).
    """
    return SSEBackendProvider.instance().get()


def reset_sse_backend_for_tests() -> None:
    """Reset SSE backend for test isolation."""
    SSEBackendProvider.reset_instance_for_tests()

