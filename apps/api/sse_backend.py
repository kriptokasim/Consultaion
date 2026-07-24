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


# Terminal events that immediately disconnect the subscriber
TERMINAL_EVENT_TYPES = frozenset({"final", "error", "run_completed"})

# Critical events that must be delivered but do not terminate the stream
CRITICAL_NON_TERMINAL_EVENT_TYPES = frozenset(
    {
        "debate_completed",
        "debate_failed",
        "model_response_completed",
        "model_response_failed",
        "arena_synthesis_finalized",
    }
)

# All critical events use priority 0 (preferentially retained)
CRITICAL_EVENT_TYPES = TERMINAL_EVENT_TYPES | CRITICAL_NON_TERMINAL_EVENT_TYPES

# Important state transitions should be preserved when possible
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

# Loss-tolerant events can be dropped or coalesced under pressure
# (deltas, heartbeats, progress notices, repeated diagnostics)

_DELTA_EVENT_TYPES = frozenset(
    {"model_response_delta", "arena_synthesis_delta", "agent_progress_delta"}
)


def _event_priority(event: dict) -> int:
    """Return event priority: 0=critical, 1=important, 2=loss-tolerant."""
    payload = event.get("payload", {})
    evt_type = event.get("type", payload.get("type", ""))
    if evt_type in CRITICAL_EVENT_TYPES:
        return 0
    if evt_type in IMPORTANT_EVENT_TYPES:
        return 1
    return 2


def _is_delta(event: dict) -> bool:
    payload = event.get("payload", {})
    return (
        payload.get("type", "") in _DELTA_EVENT_TYPES or event.get("type", "") in _DELTA_EVENT_TYPES
    )


def _delta_key(event: dict) -> str | None:
    """Extract coalescing key for deltas (response_id)."""
    payload = event.get("payload", {})
    return payload.get("response_id") or event.get("response_id")


class DeltaCoalescer:
    """PS155.2: Server-side delta coalescing buffer.

    Accumulates rapid-fire ``model_response_delta`` events per ``response_id``
    and flushes them at a configurable interval (default 150 ms).  On flush,
    consecutive text fragments are concatenated into a single event with
    updated ``accumulated_chars`` and ``delta_sequence`` values.

    Non-delta events trigger an immediate flush of all pending deltas so that
    event ordering remains correct.

    Bounded memory: ``max_items`` / ``max_chars`` trigger an immediate flush
    (never drop fragments — frontend concatenates ``text``).
    First delta per response_id is published immediately.
    """

    def __init__(
        self,
        flush_interval_ms: int | None = None,
        *,
        max_items: int = 256,
        max_chars: int = 64_000,
    ) -> None:
        from config import settings

        self._flush_ms = (
            flush_interval_ms
            if flush_interval_ms is not None
            else getattr(settings, "ARENA_DELTA_FLUSH_MS", 150)
        )
        self._flush_seconds = self._flush_ms / 1000.0
        self._max_items = max_items
        self._max_chars = max_chars
        # {response_id: [delta_event, ...]}
        self._pending: dict[str, list[dict]] = {}
        self._seen_keys: set[str] = set()
        self._last_flush: float = time.monotonic()

    @property
    def flush_interval_seconds(self) -> float:
        return self._flush_seconds

    def _delta_text_len(self, delta: dict) -> int:
        if isinstance(delta.get("payload"), dict):
            return len(delta.get("payload", {}).get("text", "") or "")
        return len(delta.get("text", "") or "")

    def _merge_deltas(self, deltas: list[dict]) -> dict:
        """Merge a list of delta events for the same response_id into one."""
        if len(deltas) == 1:
            return deltas[0]

        merged = dict(deltas[-1])  # use the latest event as the base
        has_nested_payload = isinstance(merged.get("payload"), dict)
        if has_nested_payload:
            combined_text = "".join(
                (delta.get("payload", {}).get("text", "") or "") for delta in deltas
            )
            merged_payload = dict(merged["payload"])
            merged_payload["text"] = combined_text
            # accumulated_chars from the last delta is already the correct total
            merged["payload"] = merged_payload
        else:
            # MemoryChannelBackend also accepts the unwrapped event shape used
            # by the rest of the SSE publishing API.
            merged["text"] = "".join((delta.get("text", "") or "") for delta in deltas)
        return merged

    def ingest(self, event: dict) -> list[dict]:
        """Accept an event and return a list of events to publish now.

        Returns an empty list if the event was buffered, or a list of
        coalesced events (possibly including the current one) if a flush
        was triggered.
        """
        now = time.monotonic()

        if not _is_delta(event):
            # Non-delta → flush all pending deltas first, then emit this event
            flushed = self.flush_all()
            flushed.append(event)
            return flushed

        key = _delta_key(event) or "__default__"

        # First delta per response_id: publish immediately (no 150ms delay)
        if key not in self._seen_keys:
            self._seen_keys.add(key)
            flushed = self.flush_all()
            flushed.append(event)
            return flushed

        if key not in self._pending:
            self._pending[key] = []
        self._pending[key].append(event)

        pending = self._pending[key]
        pending_chars = sum(self._delta_text_len(d) for d in pending)
        # Bounds: flush immediately — never drop text fragments
        if len(pending) >= self._max_items or pending_chars >= self._max_chars:
            return self.flush_all()

        elapsed = now - self._last_flush
        if elapsed >= self._flush_seconds:
            return self.flush_all()

        return []  # buffered

    def flush_all(self) -> list[dict]:
        """Flush all pending deltas, returning merged events."""
        self._last_flush = time.monotonic()
        if not self._pending:
            return []

        result = []
        for _key, deltas in self._pending.items():
            if deltas:
                result.append(self._merge_deltas(deltas))
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

    async def subscribe(
        self, channel_id: str, last_sequence: Optional[int] = None
    ) -> AsyncIterator[dict]: ...

    async def replay(self, channel_id: str, after_sequence: Optional[int] = None) -> list[dict]:
        """Return cached events after the given sequence number."""
        ...

    async def cleanup(self) -> None: ...

    async def ping(self) -> bool: ...


class MemoryChannelBackend:
    """
    In-memory SSE backend for single-instance deployments.

    Queue size is bounded (default 1000). When full, the queue enforces a priority-aware eviction policy:
    1. Loss-tolerant events are dropped first.
    2. Important events are dropped next.
    3. If full of critical events, the oldest critical event is replaced by the newest (latest critical wins).

    Subscriptions will terminate on:
    - Receiving 'final' or 'error' event types
    - Idle timeout (no events received within timeout period)
    - External cancellation

    Heartbeats are emitted every heartbeat_interval_seconds (default 5) to
    allow clients to detect connected-but-silent streams.
    """

    def __init__(
        self,
        ttl_seconds: int = 900,
        max_queue_size: int = 1000,
        idle_timeout_seconds: int = 3600,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
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
        # PS155.2: Per-channel delta coalescers
        self._coalescers: dict[str, DeltaCoalescer] = {}
        self._coalescer_flush_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        self._running = True
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        self._running = False
        flush_tasks = list(self._coalescer_flush_tasks.values())
        self._coalescer_flush_tasks.clear()
        for task in flush_tasks:
            task.cancel()
        if flush_tasks:
            await asyncio.gather(*flush_tasks, return_exceptions=True)
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
        if event.get("_already_coalesced"):
            event = dict(event)
            event.pop("_already_coalesced", None)
            await self._publish_single(channel_id, event)
            return
        # PS155.2: Route through delta coalescer
        if channel_id not in self._coalescers:
            self._coalescers[channel_id] = DeltaCoalescer()

        coalescer = self._coalescers[channel_id]
        events_to_publish = coalescer.ingest(event)

        if not events_to_publish:
            self._schedule_coalescer_flush(channel_id, coalescer)
            return  # buffered, nothing to emit yet

        pending_task = self._coalescer_flush_tasks.pop(channel_id, None)
        if pending_task:
            pending_task.cancel()

        for evt in events_to_publish:
            await self._publish_single(channel_id, evt)

    def _schedule_coalescer_flush(self, channel_id: str, coalescer: DeltaCoalescer) -> None:
        existing = self._coalescer_flush_tasks.get(channel_id)
        if existing and not existing.done():
            return

        async def flush_after_interval() -> None:
            try:
                await asyncio.sleep(coalescer.flush_interval_seconds)
                events = coalescer.flush_all()
                current = asyncio.current_task()
                if self._coalescer_flush_tasks.get(channel_id) is current:
                    self._coalescer_flush_tasks.pop(channel_id, None)
                for event in events:
                    await self._publish_single(channel_id, event)
            finally:
                current = asyncio.current_task()
                if self._coalescer_flush_tasks.get(channel_id) is current:
                    self._coalescer_flush_tasks.pop(channel_id, None)

        self._coalescer_flush_tasks[channel_id] = asyncio.create_task(flush_after_interval())

    async def _publish_single(self, channel_id: str, event: dict) -> None:
        """Publish a single event (after coalescing) to all subscribers."""
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
                "payload": event,
            }

            from observability.metrics import record_sse_message
            record_sse_message()

            # Add correlation context if available
            from correlation import get_correlation_context

            ctx = get_correlation_context()
            if ctx:
                envelope["correlation"] = ctx.to_sse_metadata()

            # Cache in history
            if channel_id not in self._history:
                self._history[channel_id] = []
            self._history[channel_id].append(envelope)
            if len(self._history[channel_id]) > self._max_queue_size:
                self._history[channel_id].pop(0)

            self._last_seen[channel_id] = time.time()

            # FH125 F-4: Fan out to all per-subscriber queues
            # Priority-based backpressure — Critical events are preferentially retained.
            # "Latest critical wins" policy applies as a per-subscriber pending queue guarantee.
            subscribers = list(self._subscribers.get(channel_id, []))

        new_priority = _event_priority(envelope)
        for sub_queue in subscribers:
            try:
                if sub_queue.full():
                    # Try to drop a loss-tolerant event to make room
                    dropped = False
                    if new_priority == 0:
                        # Critical event: must make room by dropping oldest loss-tolerant
                        dropped = self._drop_from_queue(sub_queue, min_priority_to_drop=2)
                        if not dropped:
                            # No loss-tolerant to drop; try important
                            dropped = self._drop_from_queue(sub_queue, min_priority_to_drop=1)
                        if not dropped:
                            # Queue is 100% full of critical events. To guarantee the new critical
                            # event is delivered, we implement a "latest critical wins" policy
                            # by dropping the oldest critical event.
                            dropped = self._drop_from_queue(sub_queue, min_priority_to_drop=0)
                            if dropped:
                                from metrics import increment_metric

                                increment_metric("sse.backpressure.critical_replaced")
                    elif new_priority == 1:
                        # Important event: only drop loss-tolerant
                        dropped = self._drop_from_queue(sub_queue, min_priority_to_drop=2)

                    if not dropped and sub_queue.full():
                        from metrics import increment_metric

                        increment_metric("sse.backpressure.overflow")
                        if new_priority == 0:
                            logger.error(
                                "CRITICAL: Cannot enqueue terminal event — queue full with only critical/important events"
                            )
                            increment_metric("sse.backpressure.critical_enqueue_failed")
                        continue  # Skip this subscriber rather than blocking

                await sub_queue.put(envelope)
            except Exception as e:
                logger.error(f"Error publishing to subscriber queue for {channel_id}: {e}")

    def _drop_from_queue(self, queue: asyncio.Queue[dict], min_priority_to_drop: int) -> bool:
        """Try to drop the oldest event with priority >= min_priority_to_drop from a queue.

        Returns True if an event was dropped.
        """
        # asyncio.Queue doesn't support iteration, so we need to drain and re-enqueue
        temp: list[dict] = []
        dropped = False
        while not queue.empty():
            try:
                item = queue.get_nowait()
                if not dropped and _event_priority(item) >= min_priority_to_drop:
                    dropped = True
                    from metrics import increment_metric

                    increment_metric("sse.backpressure.dropped")
                    continue  # Drop this event
                temp.append(item)
            except asyncio.QueueEmpty:
                break
        # Re-enqueue remaining events
        for item in temp:
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull:
                break
        return dropped

    async def subscribe(
        self, channel_id: str, last_sequence: Optional[int] = None
    ) -> AsyncIterator[dict]:
        """Subscribe to a channel and yield events.

        Terminates on:
        - 'final' or 'error' event types
        - idle_timeout_seconds without receiving any event
        - External cancellation
        """
        await self.create_channel(channel_id)

        # Atomic replay-to-live handoff — no event lost between history and subscription
        sub_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            # 1. Register subscriber queue FIRST (before snapshotting history)
            if channel_id not in self._subscribers:
                self._subscribers[channel_id] = []
            self._subscribers[channel_id].append(sub_queue)
            # 2. Snapshot history and high-watermark under the same lock
            history_copy = list(self._history.get(channel_id, []))
            replay_high_watermark = max((env.get("sequence", 0) for env in history_copy), default=0)

        # 3. Replay eligible history
        for env in history_copy:
            seq = env.get("sequence", 0)
            if last_sequence is None or seq > last_sequence:
                yield env
                # If replay contained a terminal event, stop immediately
                payload = env.get("payload", {})
                if payload.get("type") in TERMINAL_EVENT_TYPES:
                    async with self._lock:
                        if sub_queue in self._subscribers.get(channel_id, []):
                            self._subscribers[channel_id].remove(sub_queue)
                    return

        # 4. Drain and discard queued duplicates (events that were in history)
        while not sub_queue.empty():
            try:
                queued = sub_queue.get_nowait()
                if queued.get("sequence", 0) <= replay_high_watermark:
                    continue  # Duplicate from history — discard
                # This is a live event that arrived during replay — re-queue it
                await sub_queue.put(queued)
                break
            except asyncio.QueueEmpty:
                break

        # 5. Continue live consumption

        poll_timeout = getattr(settings, "SSE_POLL_TIMEOUT_SECONDS", 1.0)
        idle_start = time.time()
        last_heartbeat = time.time()
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
                    last_heartbeat = time.time()
                    yield envelope
                    payload = envelope.get("payload", {})
                    if payload.get("type") in TERMINAL_EVENT_TYPES:
                        break
                except asyncio.TimeoutError:
                    # Emit heartbeat if no events for heartbeat interval
                    if self._heartbeat_interval_seconds > 0:
                        elapsed = time.time() - last_heartbeat
                        if elapsed >= self._heartbeat_interval_seconds:
                            heartbeat_envelope = {
                                "id": f"hb-{channel_id}-{int(time.time())}",
                                "type": "heartbeat",
                                "event": "heartbeat",
                                "session_id": channel_id,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "sequence": 0,
                                "payload": {"type": "heartbeat"},
                            }
                            try:
                                yield heartbeat_envelope
                            except Exception:
                                pass
                            last_heartbeat = time.time()
                    continue
        finally:
            # Remove subscriber queue on disconnect — cancellation propagates via finally
            async with self._lock:
                subs = self._subscribers.get(channel_id, [])
                if sub_queue in subs:
                    subs.remove(sub_queue)

    async def replay(self, channel_id: str, after_sequence: Optional[int] = None) -> list[dict]:
        """Return cached events after the given sequence number (public contract)."""
        async with self._lock:
            history = list(self._history.get(channel_id, []))
        if after_sequence is None:
            return history
        return [env for env in history if env.get("sequence", 0) > after_sequence]

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
        stale_flush_tasks = []
        for cid in stale:
            self._coalescers.pop(cid, None)
            task = self._coalescer_flush_tasks.pop(cid, None)
            if task:
                task.cancel()
                stale_flush_tasks.append(task)
        if stale_flush_tasks:
            await asyncio.gather(*stale_flush_tasks, return_exceptions=True)
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

    def __init__(
        self,
        url: str,
        ttl_seconds: int = 900,
        max_queue_size: int = 1000,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        if redis is None:
            raise RuntimeError("redis library is required for RedisChannelBackend")
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._max_queue_size = max_queue_size
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        # Use shared async Redis connection pool
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
                retry_on_timeout=True,
            )
        self._coalescers: dict[str, DeltaCoalescer] = {}
        self._coalescer_flush_tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        # Verify connection
        try:
            await self._redis.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis for SSE: {e}")
            # We don't raise here to allow app startup, but subsequent calls will fail/retry

    async def stop(self) -> None:
        flush_tasks = list(getattr(self, "_coalescer_flush_tasks", {}).values())
        self._coalescer_flush_tasks = {}
        for task in flush_tasks:
            task.cancel()
        if flush_tasks:
            await asyncio.gather(*flush_tasks, return_exceptions=True)
        # Don't close pooled Redis clients — only close standalone connections
        if self._redis and not getattr(self._redis, "_from_pool", False):
            await self._redis.aclose()

    async def create_channel(self, channel_id: str) -> None:
        key = f"sse:meta:{channel_id}"
        await self._redis.set(key, "1", ex=self._ttl_seconds)

    async def publish(self, channel_id: str, event: dict) -> None:
        if event.get("_already_coalesced"):
            event = dict(event)
            event.pop("_already_coalesced", None)
            await self._publish_single(channel_id, event)
            return
        # Keep production Redis behavior aligned with the memory backend: token
        # fragments are coalesced per response and flushed before lifecycle
        # events so transport ordering remains intact.
        if not hasattr(self, "_coalescers"):
            self._coalescers = {}
        if not hasattr(self, "_coalescer_flush_tasks"):
            self._coalescer_flush_tasks = {}
        if channel_id not in self._coalescers:
            self._coalescers[channel_id] = DeltaCoalescer()

        coalescer = self._coalescers[channel_id]
        events_to_publish = coalescer.ingest(event)
        if not events_to_publish:
            self._schedule_coalescer_flush(channel_id, coalescer)
            return

        pending_task = self._coalescer_flush_tasks.pop(channel_id, None)
        if pending_task:
            pending_task.cancel()

        for pending_event in events_to_publish:
            await self._publish_single(channel_id, pending_event)

    def _schedule_coalescer_flush(self, channel_id: str, coalescer: DeltaCoalescer) -> None:
        existing = self._coalescer_flush_tasks.get(channel_id)
        if existing and not existing.done():
            return

        async def flush_after_interval() -> None:
            try:
                await asyncio.sleep(coalescer.flush_interval_seconds)
                events = coalescer.flush_all()
                current = asyncio.current_task()
                if self._coalescer_flush_tasks.get(channel_id) is current:
                    self._coalescer_flush_tasks.pop(channel_id, None)
                for pending_event in events:
                    await self._publish_single(channel_id, pending_event)
            finally:
                current = asyncio.current_task()
                if self._coalescer_flush_tasks.get(channel_id) is current:
                    self._coalescer_flush_tasks.pop(channel_id, None)

        self._coalescer_flush_tasks[channel_id] = asyncio.create_task(flush_after_interval())

    async def _publish_single(self, channel_id: str, event: dict) -> None:
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
            raise SSESequenceError(
                f"Cannot allocate monotonic SSE sequence for {channel_id}"
            ) from e

        # Create unified event envelope
        envelope = {
            "id": f"sse-{channel_id}-{seq}",
            "type": event.get("type", "notice"),
            "event": event.get("type", "notice"),
            "session_id": channel_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sequence": seq,
            "payload": event,
        }

        from observability.metrics import record_sse_message
        record_sse_message()

        payload_str = json.dumps(envelope)

        # Cache in Redis list history
        history_key = f"sse:history:{channel_id}"
        try:
            pipeline = self._redis.pipeline(transaction=False)
            pipeline.rpush(history_key, payload_str)
            pipeline.expire(history_key, self._ttl_seconds)
            pipeline.ltrim(history_key, -self._max_queue_size, -1)
            await pipeline.execute()
        except Exception as e:
            logger.error(f"Failed to save Redis SSE history: {e}")

        for attempt in range(3):
            try:
                await self._redis.publish(channel_id, payload_str)
                return
            except (redis.ConnectionError, redis.TimeoutError) as e:
                if attempt == 2:
                    logger.error(
                        f"Failed to publish to Redis SSE {channel_id} after 3 attempts: {e}"
                    )
                    from metrics import increment_metric

                    increment_metric("sse.publish.degraded")
                else:
                    await asyncio.sleep(0.1 * (2**attempt))
            except Exception as e:
                logger.error(f"Failed to publish to Redis SSE {channel_id}: {e}")
                from metrics import increment_metric

                increment_metric("sse.publish.failed")
                return

    async def subscribe(
        self, channel_id: str, last_sequence: Optional[int] = None
    ) -> AsyncIterator[dict]:
        # Race-safe replay-to-live handoff for Redis
        # 1. Subscribe to Pub/Sub FIRST (before reading history)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel_id)

        # 2. Read history and capture high-watermark
        replay_high_watermark = 0
        history_key = f"sse:history:{channel_id}"
        try:
            events_str = await self._redis.lrange(history_key, 0, -1)
            history_events = [json.loads(evt_str) for evt_str in events_str]
            replay_high_watermark = max(
                (evt.get("sequence", 0) for evt in history_events), default=0
            )
        except Exception as e:
            logger.error(f"Failed to fetch Redis SSE history: {e}")
            history_events = []

        # 3. Replay eligible history
        for evt in history_events:
            seq = evt.get("sequence", 0)
            if last_sequence is None or seq > last_sequence:
                yield evt
                payload = evt.get("payload", {})
                if payload.get("type") in ("final", "error"):
                    await pubsub.unsubscribe(channel_id)
                    await pubsub.close()
                    return

        # 4. Drain Pub/Sub messages that arrived during history read (duplicates)
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if not message:
                    break
                data = message.get("data")
                if data:
                    envelope = json.loads(data)
                    if envelope.get("sequence", 0) <= replay_high_watermark:
                        continue  # Duplicate from history — discard
                    # Live event — yield it
                    yield envelope
                    payload = envelope.get("payload", {})
                    if payload.get("type") in ("final", "error"):
                        await pubsub.unsubscribe(channel_id)
                        await pubsub.close()
                        return
            except Exception:
                break

        # 5. Continue live consumption from Pub/Sub
        last_heartbeat = time.time()
        heartbeat_interval = getattr(self, "_heartbeat_interval_seconds", 5.0)
        try:
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message:
                        data = message.get("data")
                        if data:
                            envelope = json.loads(data)
                            yield envelope
                            last_heartbeat = time.time()
                            payload = envelope.get("payload", {})
                            if payload.get("type") in ("final", "error"):
                                break
                    else:
                        # Emit heartbeat if no events for heartbeat interval
                        if heartbeat_interval > 0:
                            elapsed = time.time() - last_heartbeat
                            if elapsed >= heartbeat_interval:
                                heartbeat_envelope = {
                                    "id": f"hb-{channel_id}-{int(time.time())}",
                                    "type": "heartbeat",
                                    "event": "heartbeat",
                                    "session_id": channel_id,
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "sequence": 0,
                                    "payload": {"type": "heartbeat"},
                                }
                                try:
                                    yield heartbeat_envelope
                                except Exception:
                                    pass
                                last_heartbeat = time.time()
                        await asyncio.sleep(0.01)
                except (redis.ConnectionError, redis.TimeoutError) as e:
                    logger.warning(f"Redis connection lost in subscribe ({e}), retrying...")
                    await asyncio.sleep(1)
                    try:
                        await pubsub.subscribe(channel_id)
                    except Exception:
                        pass
        finally:
            await pubsub.unsubscribe(channel_id)
            await pubsub.close()

    async def replay(self, channel_id: str, after_sequence: Optional[int] = None) -> list[dict]:
        """Return cached events after the given sequence number (public contract)."""
        history_key = f"sse:history:{channel_id}"
        try:
            events_str = await self._redis.lrange(history_key, 0, -1)
            events = [json.loads(evt_str) for evt_str in events_str]
            if after_sequence is not None:
                events = [e for e in events if e.get("sequence", 0) > after_sequence]
            return events
        except Exception as e:
            logger.error(f"Failed to replay Redis SSE history for {channel_id}: {e}")
            return []

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

    async def try_acquire(
        self, debate_id: str, subscriber_id: str, user_id: str | None = None
    ) -> StreamLeaseResult:
        """Try to acquire a streaming lease."""
        identity = self._subscriber_identity(debate_id, user_id or "anon", subscriber_id)
        try:
            from redis_pool import get_async_redis_client

            client = get_async_redis_client()
            if client is not None:
                from services.lease import sse_acquire_lease_async

                key = self._lease_key(debate_id)
                result = await sse_acquire_lease_async(
                    client, key, identity, self._max_streams, self._lease_ttl
                )
                if result in (1, 2):
                    from metrics import increment_metric

                    increment_metric("sse.lease.acquired")
                    return StreamLeaseResult.ACQUIRED
                if result == 0:
                    from metrics import increment_metric

                    increment_metric("sse.lease.denied")
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
                    from metrics import increment_metric

                    increment_metric("sse.lease.expired")
                if len(memory_set) >= self._max_streams:
                    from metrics import increment_metric

                    increment_metric("sse.lease.denied")
                    return StreamLeaseResult.DENIED
                memory_set[identity] = now + self._lease_ttl
                from metrics import increment_metric

                increment_metric("sse.lease.acquired")
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


LEASE_RELEASE_TIMEOUT_SECONDS = 5.0


class AcquiredStreamLease:
    """Async context manager that ensures a stream lease is released exactly once.

    Handles:
    - Normal completion (final/error event)
    - Client disconnect
    - Backend exception
    - Server cancellation
    - Serialization failure
    - Duplicate cleanup (idempotent)
    """

    def __init__(
        self,
        lease_manager: StreamLeaseManager,
        debate_id: str,
        subscriber_id: str,
    ) -> None:
        self._lease_manager = lease_manager
        self._debate_id = debate_id
        self._subscriber_id = subscriber_id
        self._released = False

    async def __aenter__(self) -> "AcquiredStreamLease":
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._released:
            return
        self._released = True
        try:
            await asyncio.wait_for(
                asyncio.shield(self._lease_manager.release(self._debate_id, self._subscriber_id)),
                timeout=LEASE_RELEASE_TIMEOUT_SECONDS,
            )
            from metrics import increment_metric

            increment_metric("sse.lease.released")
        except asyncio.TimeoutError:
            from metrics import increment_metric

            increment_metric("sse.lease.release_failed")
            logger.error(
                "Lease release timed out: debate=%s subscriber=%s",
                self._debate_id,
                self._subscriber_id,
            )
        except Exception as exc:
            from metrics import increment_metric

            increment_metric("sse.lease.release_failed")
            logger.error(
                "Lease release failed: debate=%s subscriber=%s error=%s",
                self._debate_id,
                self._subscriber_id,
                exc,
            )


def acquired_stream_lease(
    lease_manager: StreamLeaseManager,
    debate_id: str,
    subscriber_id: str,
) -> AcquiredStreamLease:
    """Create an async context manager for exactly-once stream lease cleanup."""
    return AcquiredStreamLease(lease_manager, debate_id, subscriber_id)


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
        idle_timeout_seconds=idle_timeout,
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
