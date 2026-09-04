from __future__

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

# Terminal events that immediately disconnect the subscriber
TERMINAL_EVENT_TYPES = frozenset({"final", "error", "run_completed", "cancelled"})

CRITICAL_NON_TERMINAL_EVENT_TYPES = frozenset(
    {
        "debate_completed",
        "debate_failed",
        "model_response_completed",
        "model_response_failed",
        "arena_synthesis_finalized",
    }
)
CRITICAL_EVENT_TYPES = TERMINAL_EVENT_TYPES | CRITICAL_NON_TERMINAL_EVENT_TYPES
IMPORTANT_EVENT_TYPES = frozenset(
    {
        "arena_response",
        "arena_synthesis_started",
        "arena_synthesis_revision",
        "perspectives_ready",
        "stage_checkpoint",
        "lane_assigned",
        "lane_convergence_checked",
    }
)
_DELTA_EVENT_TYPES = frozenset({"model_response_delta", "arena_synthesis_delta", "agent_progress_delta"})


def _event_priority(event: dict) -> int:
    payload = event.get("payload", {})
    evt_type = event.get("type", payload.get("type", ""))
    if evt_type in CRITICAL_EVENT_TYPES:
        return 0
    if evt_type in IMPORTANT_EVENT_TYPES:
        return 1
    return 2


def _is_delta(event: dict) -> bool:
    payload = event.get("payload", {})
    return payload.get("type", "") in _DELTA_EVENT_TYPES or event.get("type", "") in _DELTA_EVENT_TYPES


def _delta_key(event: dict) -> str | None:
    payload = event.get("payload", {})
    return payload.get("response_id") or event.get("response_id")


class DeltaCoalescer:
    def __init__(self, flush_interval_ms: int | None = None, *, max_items: int = 256, max_chars: int = 64_000) -> None:
        self._flush_ms = flush_interval_ms if flush_interval_ms is not None else getattr(settings, "ARENA_DELTA_FLUSH_MS", 150)
        self._flush_seconds = self._flush_ms / 1000.0
        self._max_items = max_items
        self._max_chars = max_chars
        self._pending: dict[str, list[dict]] = {}
        self._seen_keys: set[str] = set()
        self._last_flush = time.monotonic()

    @property
    def flush_interval_seconds(self) -> float:
        return self._flush_seconds

    def _delta_text_len(self, delta: dict) -> int:
        payload = delta.get("payload")
        return len((payload.get("text", "") if isinstance(payload, dict) else delta.get("text", "")) or "")

    def _merge_deltas(self, deltas: list[dict]) -> dict:
        if len(deltas) == 1:
            return deltas[0]
        merged = dict(deltas[-1])
        if isinstance(merged.get("payload"), dict):
            payload = dict(merged["payload"])
            payload["text"] = "".join((d.get("payload", {}).get("text", "") or "") for d in deltas)
            merged["payload"] = payload
        else:
            merged["text"] = "".join((d.get("text", "") or "") for d in deltas)
        return merged

    def ingest(self, event: dict) -> list[dict]:
        now = time.monotonic()
        if not _is_delta(event):
            flushed = self.flush_all()
            flushed.append(event)
            return flushed
        key = _delta_key(event) or "__default__"
        if key not in self._seen_keys:
            self._seen_keys.add(key)
            flushed = self.flush_all()
            flushed.append(event)
            return flushed
        self._pending.setdefault(key, []).append(event)
        pending = self._pending[key]
        if len(pending) >= self._max_items or sum(self._delta_text_len(d) for d in pending) >= self._max_chars:
            return self.flush_all()
        if now - self._last_flush >= self._flush_seconds:
            return self.flush_all()
        return []

    def flush_all(self) -> list[dict]:
        self._last_flush = time.monotonic()
        result = [self._merge_deltas(deltas) for deltas in self._pending.values() if deltas]
        self._pending.clear()
        return result


class StreamLeaseResult(Enum):
    ACQUIRED = "acquired"
    DENIED = "denied"
    ERROR_FAIL_OPEN = "error_fail_open"
    ERROR_FAIL_CLOSED = "error_fail_closed"


class SSESequenceError(RuntimeError):
    """A durable monotonic SSE event identity could not be allocated."""


class BaseSSEBackend(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def create_channel(self, channel_id: str) -> None: ...
    async def publish(self, channel_id: str, event: dict) -> None: ...
    async def subscribe(self, channel_id: str, last_sequence: Optional[int] = None) -> AsyncIterator[dict]: ...
    async def replay(self, channel_id: str, after_sequence: Optional[int] = None) -> list[dict]: ...
    async def cleanup(self) -> None: ...
    async def ping(self) -> bool: ...


class MemoryChannelBackend:
    def __init__(self, ttl_seconds: int = 900, max_queue_size: int = 1000, idle_timeout_seconds: int = 3600, heartbeat_interval_seconds: float = 5.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_queue_size = max_queue_size
        self._idle_timeout_seconds = idle_timeout_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._channels: dict[str, asyncio.Queue[dict]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = {}
        self._last_seen: dict[str, float] = {}
        self._sequences: dict[str, int] = {}
        self._history: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._coalescers: dict[str, DeltaCoalescer] = {}
        self._coalescer_flush_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        self._running = False
        tasks = list(self._coalescer_flush_tasks.values())
        self._coalescer_flush_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _periodic_cleanup(self) -> None:
        while self._running:
            await asyncio.sleep(60)
            await self.cleanup()

    async def create_channel(self, channel_id: str) -> None:
        async with self._lock:
            self._channels.setdefault(channel_id, asyncio.Queue(maxsize=self._max_queue_size))
            self._sequences.setdefault(channel_id, 0)
            self._history.setdefault(channel_id, [])
            self._last_seen[channel_id] = time.time()

    async def publish(self, channel_id: str, event: dict) -> None:
        if event.get("_already_coalesced"):
            event = dict(event)
            event.pop("_already_coalesced", None)
            await self._publish_single(channel_id, event)
            return
        coalescer = self._coalescers.setdefault(channel_id, DeltaCoalescer())
        events = coalescer.ingest(event)
        if not events:
            self._schedule_coalescer_flush(channel_id, coalescer)
            return
        task = self._coalescer_flush_tasks.pop(channel_id, None)
        if task:
            task.cancel()
        for evt in events:
            await self._publish_single(channel_id, evt)

    def _schedule_coalescer_flush(self, channel_id: str, coalescer: DeltaCoalescer) -> None:
        existing = self._coalescer_flush_tasks.get(channel_id)
        if existing and not existing.done():
            return
        async def flush_after_interval() -> None:
            try:
                await asyncio.sleep(coalescer.flush_interval_seconds)
                for event in coalescer.flush_all():
                    await self._publish_single(channel_id, event)
            finally:
                current = asyncio.current_task()
                if self._coalescer_flush_tasks.get(channel_id) is current:
                    self._coalescer_flush_tasks.pop(channel_id, None)
        self._coalescer_flush_tasks[channel_id] = asyncio.create_task(flush_after_interval())

    async def _publish_single(self, channel_id: str, event: dict) -> None:
        async with self._lock:
            seq = self._sequences.get(channel_id, 0) + 1
            self._sequences[channel_id] = seq
            envelope = {"id": f"sse-{channel_id}-{seq}", "type": event.get("type", "notice"), "event": event.get("type", "notice"), "session_id": channel_id, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sequence": seq, "payload": event}
            from observability.metrics import record_sse_message
            record_sse_message()
            from correlation import get_correlation_context
            ctx = get_correlation_context()
            if ctx:
                envelope["correlation"] = ctx.to_sse_metadata()
            history = self._history.setdefault(channel_id, [])
            history.append(envelope)
            if len(history) > self._max_queue_size:
                history.pop(0)
            self._last_seen[channel_id] = time.time()
            subscribers = list(self._subscribers.get(channel_id, []))

        for sub_queue in subscribers:
            try:
                await self._enqueue_with_backpressure(sub_queue, envelope)
            except Exception as exc:
                logger.error("Error publishing to subscriber queue for %s: %s", channel_id, exc)

    async def _enqueue_with_backpressure(self, queue: asyncio.Queue[dict], envelope: dict) -> None:
        """Enqueue without ever dropping terminal/critical state transitions.

        Critical events have a bounded priority eviction policy. If a queue is
        saturated exclusively by critical events, the new critical event is
        still retained by replacing the oldest critical event. A terminal event
        therefore cannot be lost merely because a slow client exhausted its queue.
        """
        new_priority = _event_priority(envelope)
        if queue.full():
            dropped = self._drop_from_queue(queue, 2 if new_priority <= 1 else 2)
            if not dropped and new_priority == 0:
                dropped = self._drop_from_queue(queue, 1)
            if not dropped and new_priority == 0:
                dropped = self._drop_from_queue(queue, 0)
            if not dropped:
                from metrics import increment_metric
                increment_metric("sse.backpressure.overflow")
                # For loss-tolerant events, dropping is intentional. For an
                # important event, drop it rather than blocking the publisher;
                # for critical events the priority-0 eviction above guarantees
                # room unless queue accounting itself is corrupted.
                if new_priority == 0:
                    raise RuntimeError("critical SSE queue could not make room")
                return
        queue.put_nowait(envelope)

    def _drop_from_queue(self, queue: asyncio.Queue[dict], min_priority_to_drop: int) -> bool:
        temp: list[dict] = []
        dropped = False
        while not queue.empty():
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if not dropped and _event_priority(item) >= min_priority_to_drop:
                dropped = True
                from metrics import increment_metric
                increment_metric("sse.backpressure.dropped")
                continue
            temp.append(item)
        for item in temp:
            queue.put_nowait(item)
        return dropped

    async def subscribe(self, channel_id: str, last_sequence: Optional[int] = None) -> AsyncIterator[dict]:
        await self.create_channel(channel_id)
        sub_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            self._subscribers.setdefault(channel_id, []).append(sub_queue)
            history_copy = list(self._history.get(channel_id, []))
            replay_high_watermark = max((env.get("sequence", 0) for env in history_copy), default=0)
        for env in history_copy:
            if last_sequence is None or env.get("sequence", 0) > last_sequence:
                yield env
                if env.get("payload", {}).get("type") in TERMINAL_EVENT_TYPES:
                    async with self._lock:
                        if sub_queue in self._subscribers.get(channel_id, []):
                            self._subscribers[channel_id].remove(sub_queue)
                    return
        while not sub_queue.empty():
            try:
                queued = sub_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if queued.get("sequence", 0) <= replay_high_watermark:
                continue
            sub_queue.put_nowait(queued)
            break
        poll_timeout = getattr(settings, "SSE_POLL_TIMEOUT_SECONDS", 1.0)
        idle_start = time.time()
        last_heartbeat = time.time()
        try:
            while True:
                if time.time() - idle_start > self._idle_timeout_seconds:
                    break
                try:
                    envelope = await asyncio.wait_for(sub_queue.get(), timeout=poll_timeout)
                    idle_start = time.time()
                    last_heartbeat = time.time()
                    yield envelope
                    if envelope.get("payload", {}).get("type") in TERMINAL_EVENT_TYPES:
                        break
                except asyncio.TimeoutError:
                    if self._heartbeat_interval_seconds > 0 and time.time() - last_heartbeat >= self._heartbeat_interval_seconds:
                        yield {"id": f"hb-{channel_id}-{int(time.time())}", "type": "heartbeat", "event": "heartbeat", "session_id": channel_id, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sequence": 0, "payload": {"type": "heartbeat"}}
                        last_heartbeat = time.time()
        finally:
            async with self._lock:
                subs = self._subscribers.get(channel_id, [])
                if sub_queue in subs:
                    subs.remove(sub_queue)

    async def replay(self, channel_id: str, after_sequence: Optional[int] = None) -> list[dict]:
        async with self._lock:
            history = list(self._history.get(channel_id, []))
        return history if after_sequence is None else [e for e in history if e.get("sequence", 0) > after_sequence]

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
        for cid in stale:
            self._coalescers.pop(cid, None)
            task = self._coalescer_flush_tasks.pop(cid, None)
            if task:
                task.cancel()
        logger.info("Cleaned up %d stale SSE channels", len(stale)) if stale else None

    async def ping(self) -> bool:
        return True


class RedisChannelBackend:
    """Redis-backed SSE backend for multi-instance deployments."""
    def __init__(self, url: str, ttl_seconds: int = 900, max_queue_size: int = 1000, heartbeat_interval_seconds: float = 5.0) -> None:
        if redis is None:
            raise RuntimeError("redis library is required for RedisChannelBackend")
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._max_queue_size = max_queue_size
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        from redis_pool import get_async_redis_client
        pooled_client = get_async_redis_client()
        if pooled_client is not None:
            self._redis = pooled_client
            self._redis._from_pool = True
        else:
            self._redis = redis.from_url(url, encoding="utf-8", decode_responses=True, socket_connect_timeout=5, socket_timeout=10, socket_keepalive=True, health_check_interval=30, retry_on_timeout=True)
        self._coalescers: dict[str, DeltaCoalescer] = {}
        self._coalescer_flush_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        try:
            await self._redis.ping()
        except Exception as exc:
            logger.error("Failed to connect to Redis for SSE: %s", exc)

    async def stop(self) -> None:
        tasks = list(self._coalescer_flush_tasks.values())
        self._coalescer_flush_tasks = {}
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self._redis and not getattr(self._redis, "_from_pool", False):
            await self._redis.aclose()

    async def create_channel(self, channel_id: str) -> None:
        await self._redis.set(f"sse:meta:{channel_id}", "1", ex=self._ttl_seconds)

    async def publish(self, channel_id: str, event: dict) -> None:
        if event.get("_already_coalesced"):
            event = dict(event)
            event.pop("_already_coalesced", None)
            await self._publish_single(channel_id, event)
            return
        coalescer = self._coalescers.setdefault(channel_id, DeltaCoalescer())
        events = coalescer.ingest(event)
        if not events:
            self._schedule_coalescer_flush(channel_id, coalescer)
            return
        task = self._coalescer_flush_tasks.pop(channel_id, None)
        if task:
            task.cancel()
        for evt in events:
            await self._publish_single(channel_id, evt)

    def _schedule_coalescer_flush(self, channel_id: str, coalescer: DeltaCoalescer) -> None:
        existing = self._coalescer_flush_tasks.get(channel_id)
        if existing and not existing.done():
            return
        async def flush_after_interval() -> None:
            try:
                await asyncio.sleep(coalescer.flush_interval_seconds)
                for evt in coalescer.flush_all():
                    await self._publish_single(channel_id, evt)
            finally:
                current = asyncio.current_task()
                if self._coalescer_flush_tasks.get(channel_id) is current:
                    self._coalescer_flush_tasks.pop(channel_id, None)
        self._coalescer_flush_tasks[channel_id] = asyncio.create_task(flush_after_interval())

    async def _publish_single(self, channel_id: str, event: dict) -> None:
        seq_key = f"sse:seq:{channel_id}"
        try:
            seq = await self._redis.incr(seq_key)
            await self._redis.expire(seq_key, self._ttl_seconds)
            if not isinstance(seq, int):
                seq = int(seq)
        except Exception as exc:
            logger.error("Failed to increment Redis sequence for %s: %s", channel_id, exc)
            raise SSESequenceError(f"Cannot allocate monotonic SSE sequence for {channel_id}") from exc
        envelope = {"id": f"sse-{channel_id}-{seq}", "type": event.get("type", "notice"), "event": event.get("type", "notice"), "session_id": channel_id, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sequence": seq, "payload": event}
        from observability.metrics import record_sse_message
        record_sse_message()
        payload_str = json.dumps(envelope)
        history_key = f"sse:history:{channel_id}"
        try:
            pipeline = self._redis.pipeline(transaction=False)
            pipeline.rpush(history_key, payload_str)
            pipeline.expire(history_key, self._ttl_seconds)
            pipeline.ltrim(history_key, -self._max_queue_size, -1)
            await pipeline.execute()
        except Exception as exc:
            logger.error("Failed to save Redis SSE history: %s", exc)
        for attempt in range(3):
            try:
                await self._redis.publish(channel_id, payload_str)
                return
            except (redis.ConnectionError, redis.TimeoutError) as exc:
                if attempt == 2:
                    logger.error("Failed to publish to Redis SSE %s after 3 attempts: %s", channel_id, exc)
                    from metrics import increment_metric
                    increment_metric("sse.publish.degraded")
                else:
                    await asyncio.sleep(0.1 * (2 ** attempt))
            except Exception as exc:
                logger.error("Failed to publish to Redis SSE %s: %s", channel_id, exc)
                from metrics import increment_metric
                increment_metric("sse.publish.failed")
                return

    async def subscribe(self, channel_id: str, last_sequence: Optional[int] = None) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel_id)
        replay_high_watermark = 0
        try:
            events_str = await self._redis.lrange(f"sse:history:{channel_id}", 0, -1)
            history_events = [json.loads(e) for e in events_str]
            replay_high_watermark = max((e.get("sequence", 0) for e in history_events), default=0)
        except Exception as exc:
            logger.error("Failed to fetch Redis SSE history: %s", exc)
            history_events = []
        for evt in history_events:
            if last_sequence is None or evt.get("sequence", 0) > last_sequence:
                yield evt
                if evt.get("payload", {}).get("type") in TERMINAL_EVENT_TYPES:
                    await pubsub.unsubscribe(channel_id)
                    await pubsub.close()
                    return
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if not message:
                    break
                data = message.get("data")
                if data:
                    envelope = json.loads(data)
                    if envelope.get("sequence", 0) <= replay_high_watermark:
                        continue
                    yield envelope
                    if envelope.get("payload", {}).get("type") in TERMINAL_EVENT_TYPES:
                        await pubsub.unsubscribe(channel_id)
                        await pubsub.close()
                        return
            except Exception:
                break
        last_heartbeat = time.time()
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data = message.get("data")
                    if data:
                        envelope = json.loads(data)
                        yield envelope
                        last_heartbeat = time.time()
                        if envelope.get("payload", {}).get("type") in TERMINAL_EVENT_TYPES:
                            break
                elif self._heartbeat_interval_seconds > 0 and time.time() - last_heartbeat >= self._heartbeat_interval_seconds:
                    yield {"id": f"hb-{channel_id}-{int(time.time())}", "type": "heartbeat", "event": "heartbeat", "session_id": channel_id, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sequence": 0, "payload": {"type": "heartbeat"}}
                    last_heartbeat = time.time()
                await asyncio.sleep(0.01)
            except (redis.ConnectionError, redis.TimeoutError) as exc:
                logger.warning("Redis connection lost in subscribe (%s), retrying...", exc)
                await asyncio.sleep(1)
                try:
                    await pubsub.subscribe(channel_id)
                except Exception:
                    pass
        await pubsub.unsubscribe(channel_id)
        await pubsub.close()

    async def replay(self, channel_id: str, after_sequence: Optional[int] = None) -> list[dict]:
        try:
            events = [json.loads(e) for e in await self._redis.lrange(f"sse:history:{channel_id}", 0, -1)]
            return events if after_sequence is None else [e for e in events if e.get("sequence", 0) > after_sequence]
        except Exception as exc:
            logger.error("Failed to replay Redis SSE history for %s: %s", channel_id, exc)
            return []

    async def cleanup(self) -> None:
        return None

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False


class StreamLeaseManager:
    """Lease-based concurrent stream limiter."""
    def __init__(self, max_streams: int = 5, lease_ttl: int = 300):
        self._max_streams = max_streams
        self._lease_ttl = lease_ttl
        self._memory_leases: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def _lease_key(self, debate_id: str) -> str:
        return f"sse:leases:{debate_id}"

    @staticmethod
    def _subscriber_identity(debate_id: str, user_id: str, subscriber_id: str) -> str:
        return f"{user_id}:{subscriber_id}"

    async def try_acquire(self, debate_id: str, subscriber_id: str, user_id: str | None = None) -> StreamLeaseResult:
        identity = self._subscriber_identity(debate_id, user_id or "anon", subscriber_id)
        try:
            from redis_pool import get_async_redis_client
            client = get_async_redis_client()
            if client is not None:
                from services.lease import sse_acquire_lease_async
                result = await sse_acquire_lease_async(client, self._lease_key(debate_id), identity, self._max_streams, self._lease_ttl)
                if result in (1, 2):
                    from metrics import increment_metric
                    increment_metric("sse.lease.acquired")
                    return StreamLeaseResult.ACQUIRED
                if result == 0:
                    from metrics import increment_metric
                    increment_metric("sse.lease.denied")
                    return StreamLeaseResult.DENIED
        except Exception as exc:
            logger.warning("Redis lease acquire failed, falling back to memory: %s", exc)
        try:
            async with self._lock:
                now = time.time()
                memory_set = self._memory_leases.setdefault(debate_id, {})
                for key in [k for k, v in memory_set.items() if v < now]:
                    del memory_set[key]
                if len(memory_set) >= self._max_streams:
                    return StreamLeaseResult.DENIED
                memory_set[identity] = now + self._lease_ttl
                return StreamLeaseResult.ACQUIRED
        except Exception as exc:
            logger.error("Memory lease acquire failed: %s", exc)
        return StreamLeaseResult.ERROR_FAIL_OPEN if getattr(settings, "SSE_LEASE_FAIL_OPEN", False) else StreamLeaseResult.ERROR_FAIL_CLOSED

    async def release(self, debate_id: str, subscriber_id: str, user_id: str | None = None) -> None:
        identity = self._subscriber_identity(debate_id, user_id or "anon", subscriber_id)
        try:
            from redis_pool import get_async_redis_client
            client = get_async_redis_client()
            if client is not None:
                from services.lease import sse_release_lease_async
                await sse_release_lease_async(client, self._lease_key(debate_id), identity)
                return
        except Exception:
            pass
        async with self._lock:
            memory_set = self._memory_leases.get(debate_id)
            if memory_set:
                memory_set.pop(identity, None)

    async def active_count(self, debate_id: str) -> int:
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
        now = time.time()
        return sum(1 for v in self._memory_leases.get(debate_id, {}).values() if v >= now)


_stream_lease_manager: StreamLeaseManager | None = None
_stream_lease_lock = asyncio.Lock()

def get_stream_lease_manager() -> StreamLeaseManager:
    global _stream_lease_manager
    if _stream_lease_manager is None:
        _stream_lease_manager = StreamLeaseManager(max_streams=getattr(settings, "SSE_MAX_CONCURRENT_STREAMS", 5), lease_ttl=getattr(settings, "SSE_LEASE_TTL_SECONDS", 300))
    return _stream_lease_manager

LEASE_RELEASE_TIMEOUT_SECONDS = 5.0

class AcquiredStreamLease:
    def __init__(self, lease_manager: StreamLeaseManager, debate_id: str, subscriber_id: str) -> None:
        self._lease_manager = lease_manager
        self._debate_id = debate_id
        self._subscriber_id = subscriber_id
        self._released = False

    async def __aenter__(self) -> "AcquiredStreamLease":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._released:
            return
        self._released = True
        try:
            await asyncio.wait_for(self._lease_manager.release(self._debate_id, self._subscriber_id), timeout=LEASE_RELEASE_TIMEOUT_SECONDS)
        except Exception as release_exc:
            logger.warning("Failed to release SSE lease for %s: %s", self._debate_id, release_exc)
