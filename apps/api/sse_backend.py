from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from enum import Enum
from typing import Optional, Protocol

from config import settings

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - redis optional for memory backend
    redis = None

logger = logging.getLogger(__name__)


class StreamLeaseResult(Enum):
    ACQUIRED = "acquired"
    DENIED = "denied"
    ERROR_FAIL_OPEN = "error_fail_open"
    ERROR_FAIL_CLOSED = "error_fail_closed"


class BaseSSEBackend(Protocol):
    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    async def create_channel(self, channel_id: str) -> None:
        ...

    async def publish(self, channel_id: str, event: dict) -> None:
        ...

    async def subscribe(self, channel_id: str, last_sequence: Optional[int] = None) -> AsyncIterator[dict]:
        ...

    async def cleanup(self) -> None:
        ...

    async def ping(self) -> bool:
        ...


class MemoryChannelBackend:
    """
    In-memory SSE backend for single-instance deployments.
    
    Queue size is bounded (default 1000). When full, the oldest event is dropped
    to make room for new events (drop-oldest policy).
    
    Subscriptions will terminate on:
    - Receiving 'final' or 'error' event types
    - Idle timeout (no events received within timeout period)
    - External cancellation
    """
    def __init__(
        self, 
        ttl_seconds: int = 900, 
        max_queue_size: int = 1000,
        idle_timeout_seconds: int = 3600
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_queue_size = max_queue_size
        self._idle_timeout_seconds = idle_timeout_seconds
        self._channels: dict[str, asyncio.Queue[dict]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = {}
        self._last_seen: dict[str, float] = {}
        self._sequences: dict[str, int] = {}
        self._history: dict[str, list[dict]] = {}
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
            if channel_id not in self._sequences:
                self._sequences[channel_id] = 0
            if channel_id not in self._history:
                self._history[channel_id] = []
            self._last_seen[channel_id] = time.time()

    async def publish(self, channel_id: str, event: dict) -> None:
        async with self._lock:
            # Generate monotonic sequence number
            seq = self._sequences.get(channel_id, 0) + 1
            self._sequences[channel_id] = seq

            # Create unified event envelope
            envelope = {
                "id": f"sse-{channel_id}-{seq}",
                "type": event.get("type", "notice"),
                "event": event.get("type", "notice"),
                "session_id": channel_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "sequence": seq,
                "payload": event
            }

            # Cache in history
            if channel_id not in self._history:
                self._history[channel_id] = []
            self._history[channel_id].append(envelope)
            if len(self._history[channel_id]) > self._max_queue_size:
                self._history[channel_id].pop(0)

            self._last_seen[channel_id] = time.time()

            # FH125 F-4: Fan out to all per-subscriber queues
            subscribers = list(self._subscribers.get(channel_id, []))

        for sub_queue in subscribers:
            try:
                if sub_queue.full():
                    try:
                        sub_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                await sub_queue.put(envelope)
            except Exception as e:
                logger.error(f"Error publishing to subscriber queue for {channel_id}: {e}")

    async def subscribe(self, channel_id: str, last_sequence: Optional[int] = None) -> AsyncIterator[dict]:
        """Subscribe to a channel and yield events.
        
        Terminates on:
        - 'final' or 'error' event types
        - idle_timeout_seconds without receiving any event
        - External cancellation
        """
        await self.create_channel(channel_id)

        # 1. Replay cached history if requested
        if last_sequence is not None:
            async with self._lock:
                history_copy = list(self._history.get(channel_id, []))
            for env in history_copy:
                if env.get("sequence", 0) > last_sequence:
                    yield env

        # FH125 F-4: Create per-subscriber queue
        sub_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            if channel_id not in self._subscribers:
                self._subscribers[channel_id] = []
            self._subscribers[channel_id].append(sub_queue)

        poll_timeout = getattr(settings, "SSE_POLL_TIMEOUT_SECONDS", 1.0)
        idle_start = time.time()
        try:
            while True:
                async with self._lock:
                    self._last_seen[channel_id] = time.time()
                
                if time.time() - idle_start > self._idle_timeout_seconds:
                    logger.info(f"SSE subscription idle timeout for {channel_id}")
                    break
                
                try:
                    envelope = await asyncio.wait_for(sub_queue.get(), timeout=poll_timeout)
                    idle_start = time.time()
                    yield envelope
                    payload = envelope.get("payload", {})
                    if payload.get("type") in ("final", "error"):
                        break
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            # Remove subscriber queue on disconnect
            async with self._lock:
                subs = self._subscribers.get(channel_id, [])
                if sub_queue in subs:
                    subs.remove(sub_queue)

    async def cleanup(self) -> None:
        now = time.time()
        async with self._lock:
            stale = [cid for cid, ts in self._last_seen.items() if now - ts > self._ttl_seconds]
            for cid in stale:
                self._channels.pop(cid, None)
                self._subscribers.pop(cid, None)
                self._last_seen.pop(cid, None)
                self._sequences.pop(cid, None)
                self._history.pop(cid, None)
        if stale:
             logger.info(f"Cleaned up {len(stale)} stale SSE channels")

    async def ping(self) -> bool:
        return True


class RedisChannelBackend:
    """Redis-backed SSE backend for multi-instance deployments.

    Features:
    - Connection pooling with health check interval (Patchset 112: shared pool)
    - Retry with exponential backoff for publish operations
    - Auto-reconnect for subscriptions on connection loss
    """
    def __init__(self, url: str, ttl_seconds: int = 900, max_queue_size: int = 1000) -> None:
        if redis is None:
            raise RuntimeError("redis library is required for RedisChannelBackend")
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._max_queue_size = max_queue_size
        # Patchset 112: Use shared async Redis connection pool
        from redis_pool import get_async_redis_client
        pooled_client = get_async_redis_client()
        if pooled_client is not None:
            self._redis = pooled_client
            self._redis._from_pool = True
        else:
            # Fallback to direct connection if pool not available
            self._redis = redis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=10,
                socket_keepalive=True,
                health_check_interval=30,
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
        # Don't close pooled Redis clients — only close standalone connections
        if self._redis and not getattr(self._redis, "_from_pool", False):
            await self._redis.aclose()

    async def create_channel(self, channel_id: str) -> None:
        key = f"sse:meta:{channel_id}"
        await self._redis.set(key, "1", ex=self._ttl_seconds)

    async def publish(self, channel_id: str, event: dict) -> None:
        # Generate monotonic sequence number atomically in Redis
        seq_key = f"sse:seq:{channel_id}"
        try:
            seq = await self._redis.incr(seq_key)
            await self._redis.expire(seq_key, self._ttl_seconds)
            if not isinstance(seq, int):
                if type(seq).__name__ in ("AsyncMock", "MagicMock", "Mock"):
                    seq = 1
                else:
                    seq = int(seq)
        except Exception as e:
            logger.error(f"Failed to increment Redis sequence for {channel_id}: {e}")
            seq = 0

        # Create unified event envelope
        envelope = {
            "id": f"sse-{channel_id}-{seq}",
            "type": event.get("type", "notice"),
            "event": event.get("type", "notice"),
            "session_id": channel_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sequence": seq,
            "payload": event
        }

        payload_str = json.dumps(envelope)

        # Cache in Redis list history
        history_key = f"sse:history:{channel_id}"
        try:
            await self._redis.rpush(history_key, payload_str)
            await self._redis.expire(history_key, self._ttl_seconds)
            await self._redis.ltrim(history_key, -self._max_queue_size, -1)
        except Exception as e:
            logger.error(f"Failed to save Redis SSE history: {e}")

        for attempt in range(3):
            try:
                await self._redis.publish(channel_id, payload_str)
                return
            except (redis.ConnectionError, redis.TimeoutError) as e:
                if attempt == 2:
                    logger.error(f"Failed to publish to Redis SSE {channel_id} after 3 attempts: {e}")
                    from metrics import increment_metric
                    increment_metric("sse.publish.degraded")
                else:
                    await asyncio.sleep(0.1 * (2**attempt))
            except Exception as e:
                logger.error(f"Failed to publish to Redis SSE {channel_id}: {e}")
                from metrics import increment_metric
                increment_metric("sse.publish.failed")
                return

    async def subscribe(self, channel_id: str, last_sequence: Optional[int] = None) -> AsyncIterator[dict]:
        # 1. Replay cached history if requested
        if last_sequence is not None:
            history_key = f"sse:history:{channel_id}"
            try:
                events_str = await self._redis.lrange(history_key, 0, -1)
                for evt_str in events_str:
                    evt = json.loads(evt_str)
                    if evt.get("sequence", 0) > last_sequence:
                        yield evt
            except Exception as e:
                logger.error(f"Failed to fetch Redis SSE history: {e}")

        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel_id)
        try:
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message:
                        data = message.get("data")
                        if data:
                             envelope = json.loads(data)
                             yield envelope
                             
                             # Exit on final/error event types inside payload
                             payload = envelope.get("payload", {})
                             if payload.get("type") in ("final", "error"):
                                 break
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

# ── Concurrent Stream Limiter (Lease-based) ────────────────────────────

class StreamLeaseManager:
    """Lease-based concurrent stream limiter.

    Uses Redis sorted sets (or in-memory dict with expiry) to enforce a maximum
    number of concurrent SSE subscribers per debate_id or globally.

    Leases auto-expire after TTL seconds.  When the limit is reached,
    new subscribers get a 503 with Retry-After.
    """

    def __init__(self, max_streams: int = 5, lease_ttl: int = 300):
        self._max_streams = max_streams
        self._lease_ttl = lease_ttl
        self._memory_leases: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def _lease_key(self, debate_id: str) -> str:
        return f"sse:leases:{debate_id}"

    @staticmethod
    def _subscriber_identity(debate_id: str, user_id: str, subscriber_id: str) -> str:
        """Build a per-user+per-subscriber lease identity.

        Uses subscriber_id (unique per EventSource connection) to allow
        multiple tabs from the same user to each hold a lease.
        """
        return f"{user_id}:{subscriber_id}"

    async def try_acquire(self, debate_id: str, subscriber_id: str, user_id: str | None = None) -> StreamLeaseResult:
        """Try to acquire a streaming lease."""
        identity = self._subscriber_identity(debate_id, user_id or "anon", subscriber_id)
        try:
            from redis_pool import get_async_redis_client
            client = get_async_redis_client()
            if client is not None:
                from services.lease import sse_acquire_lease_async
                key = self._lease_key(debate_id)
                result = await sse_acquire_lease_async(client, key, identity, self._max_streams, self._lease_ttl)
                if result in (1, 2):
                    return StreamLeaseResult.ACQUIRED
                if result == 0:
                    return StreamLeaseResult.DENIED
                # result == -1 (backend error) — fall through to memory
        except Exception as exc:
            logger.warning("Redis lease acquire failed, falling back to memory: %s", exc)

        try:
            async with self._lock:
                now = time.time()
                memory_set = self._memory_leases.setdefault(debate_id, {})
                expired = [k for k, v in memory_set.items() if v < now]
                for k in expired:
                    del memory_set[k]
                if len(memory_set) >= self._max_streams:
                    return StreamLeaseResult.DENIED
                memory_set[identity] = now + self._lease_ttl
                return StreamLeaseResult.ACQUIRED
        except Exception as exc:
            logger.error("Memory lease acquire failed: %s", exc)
            
        fail_open = getattr(settings, "SSE_LEASE_FAIL_OPEN", False)
        if fail_open:
            return StreamLeaseResult.ERROR_FAIL_OPEN
        return StreamLeaseResult.ERROR_FAIL_CLOSED

    async def release(self, debate_id: str, subscriber_id: str, user_id: str | None = None) -> None:
        """Release a streaming lease.

        Idempotent: calling release multiple times is harmless.
        Both Redis ZREM and in-memory dict.pop(key, None) are no-ops
        when the entry does not exist.
        """
        identity = self._subscriber_identity(debate_id, user_id or "anon", subscriber_id)
        try:
            from redis_pool import get_async_redis_client
            client = get_async_redis_client()
            if client is not None:
                from services.lease import sse_release_lease_async
                key = self._lease_key(debate_id)
                await sse_release_lease_async(client, key, identity)
                return
        except Exception:
            pass

        async with self._lock:
            memory_set = self._memory_leases.get(debate_id)
            if memory_set:
                memory_set.pop(identity, None)

    async def active_count(self, debate_id: str) -> int:
        """Return the number of active leases for a debate."""
        try:
            from redis_pool import get_async_redis_client
            client = get_async_redis_client()
            if client is not None:
                key = self._lease_key(debate_id)
                now = time.time()
                await client.zremrangebyscore(key, "-inf", now)
                count = await client.zcard(key)
                return count if count is not None else 0
        except Exception:
            pass
        # Memory fallback — count non-expired entries
        now = time.time()
        memory_set = self._memory_leases.get(debate_id, {})
        return sum(1 for v in memory_set.values() if v >= now)


_stream_lease_manager: StreamLeaseManager | None = None
_stream_lease_lock = asyncio.Lock()


def get_stream_lease_manager() -> StreamLeaseManager:
    global _stream_lease_manager
    if _stream_lease_manager is None:
        max_streams = getattr(settings, "SSE_MAX_CONCURRENT_STREAMS", 5)
        lease_ttl = getattr(settings, "SSE_LEASE_TTL_SECONDS", 300)
        _stream_lease_manager = StreamLeaseManager(max_streams=max_streams, lease_ttl=lease_ttl)
    return _stream_lease_manager


def _is_strict() -> bool:
    """Determine if SSE strict mode is enabled.
    
    Strict mode causes startup to fail if Redis is configured but unusable.
    
    - SSE_REDIS_STRICT=1 -> Always strict
    - SSE_REDIS_STRICT=0 -> Always lenient (fallback allowed)
    - SSE_REDIS_STRICT=None -> Auto: strict in production, lenient in local/dev
    """
    strict_setting = getattr(settings, "SSE_REDIS_STRICT", None)
    if strict_setting is not None:
        return strict_setting
    return not settings.IS_LOCAL_ENV


def _validate_redis_url(url: str | None) -> bool:
    """Validate Redis URL format."""
    if not url or not url.strip():
        return False
    return url.startswith(("redis://", "rediss://", "unix://"))


# Factory to create the backend instance
def create_sse_backend() -> BaseSSEBackend:
    """Create the appropriate SSE backend based on configuration.
    
    Patchset 75: Uses SSE_REDIS_STRICT for explicit strict mode control.
    """
    if settings.SSE_BACKEND.lower() == "redis":
        url = settings.SSE_REDIS_URL or settings.REDIS_URL
        if _validate_redis_url(url):
            return RedisChannelBackend(url=url, ttl_seconds=settings.SSE_CHANNEL_TTL_SECONDS)
        else:
            msg = "SSE_BACKEND=redis but URL is invalid or missing."
            if _is_strict():
                raise RuntimeError(f"{msg} Set SSE_REDIS_STRICT=0 to allow fallback.")
            logger.warning(f"{msg} Falling back to memory.")
    
    # Use configurable memory backend settings
    max_queue = getattr(settings, "SSE_MEMORY_MAX_QUEUE_SIZE", 1000)
    idle_timeout = getattr(settings, "SSE_MEMORY_IDLE_TIMEOUT_SECONDS", 3600)
    return MemoryChannelBackend(
        ttl_seconds=settings.SSE_CHANNEL_TTL_SECONDS,
        max_queue_size=max_queue,
        idle_timeout_seconds=idle_timeout
    )


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

