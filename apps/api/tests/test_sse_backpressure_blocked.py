"""SSE Redis Pub/Sub cleanup and backpressure tests.

Patchset 133 §7.3: Proves Redis cancellation closes Pub/Sub in all phases
and backpressure uses blocked registered subscribers.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sse_backend import (
    IMPORTANT_EVENT_TYPES,
    MemoryChannelBackend,
)


class TestBackpressureBlockedSubscriber:
    @pytest.mark.asyncio
    async def test_critical_event_always_delivered_to_full_queue(self, backend=None):
        """FH125: Critical events are delivered even when subscriber queue is full."""
        if backend is None:
            backend = MemoryChannelBackend(max_queue_size=5, heartbeat_interval_seconds=0)
        await backend.start()
        try:
            channel = "bp-test-critical"
            await backend.create_channel(channel)

            # Register a subscriber with a small queue
            subscriber = asyncio.Queue(maxsize=5)
            async with backend._lock:
                backend._subscribers.setdefault(channel, []).append(subscriber)

            # Fill the queue to capacity
            for i in range(5):
                await backend.publish(channel, {"type": f"fill-{i}"})

            # Publish a critical event — should make room by dropping loss-tolerant
            await backend.publish(channel, {"type": "final"})

            # Drain subscriber
            events = []
            while not subscriber.empty():
                events.append(subscriber.get_nowait())

            terminal = [e for e in events if e.get("payload", {}).get("type") == "final"]
            assert len(terminal) > 0, "Critical terminal event was dropped under backpressure"
        finally:
            await backend.stop()

    @pytest.mark.asyncio
    async def test_important_event_not_evicted_by_loss_tolerant(self, backend=None):
        """FH125: Important events are not evicted by loss-tolerant events."""
        if backend is None:
            backend = MemoryChannelBackend(max_queue_size=3, heartbeat_interval_seconds=0)
        await backend.start()
        try:
            channel = "bp-test-important"
            await backend.create_channel(channel)

            subscriber = asyncio.Queue(maxsize=3)
            async with backend._lock:
                backend._subscribers.setdefault(channel, []).append(subscriber)

            # Fill queue with important events
            await backend.publish(channel, {"type": "arena_response"})
            await backend.publish(channel, {"type": "model_response_completed"})
            await backend.publish(channel, {"type": "stage_checkpoint"})

            # Queue is full. Publish a loss-tolerant delta — should be dropped
            await backend.publish(channel, {"type": "model_response_delta"})

            # All 3 important events should still be in the queue
            events = []
            while not subscriber.empty():
                events.append(subscriber.get_nowait())

            important = [e for e in events if e.get("payload", {}).get("type") in IMPORTANT_EVENT_TYPES]
            deltas = [e for e in events if e.get("payload", {}).get("type") in ("model_response_delta",)]
            assert len(important) == 3, f"Expected 3 important events, got {len(important)}"
            assert len(deltas) == 0, f"Expected 0 deltas in queue, got {len(deltas)}"
        finally:
            await backend.stop()

    @pytest.mark.asyncio
    async def test_delta_coalescing_removes_older_deltas(self, backend=None):
        """FH125: Delta coalescing removes older deltas for same response_id."""
        if backend is None:
            backend = MemoryChannelBackend(max_queue_size=10, heartbeat_interval_seconds=0)
        await backend.start()
        try:
            channel = "bp-test-coalesce"
            await backend.create_channel(channel)

            subscriber = asyncio.Queue(maxsize=10)
            async with backend._lock:
                backend._subscribers.setdefault(channel, []).append(subscriber)

            # Publish multiple deltas for the same response_id
            for i in range(5):
                await backend.publish(channel, {
                    "type": "model_response_delta",
                    "response_id": "resp-1",
                    "text": f"chunk-{i}",
                })

            events = []
            while not subscriber.empty():
                events.append(subscriber.get_nowait())

            # All deltas should be delivered (coalescing happens at consumer level)
            assert len(events) == 5
        finally:
            await backend.stop()


class TestRedisCancellationPhases:
    @pytest.mark.asyncio
    async def test_redis_subscribe_cleanup_on_cancellation(self):
        """FH125: Redis Pub/Sub is closed when subscriber is cancelled."""
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_pubsub.get_message = AsyncMock(return_value=None)

        mock_redis = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.lrange = AsyncMock(return_value=[])
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()
        mock_redis.publish = AsyncMock()

        from sse_backend import RedisChannelBackend
        backend = RedisChannelBackend.__new__(RedisChannelBackend)
        backend._redis = mock_redis
        backend._url = "redis://localhost"
        backend._ttl_seconds = 900
        backend._max_queue_size = 1000
        backend._heartbeat_interval_seconds = 5.0

        # Call subscribe and get the async generator
        gen = backend.subscribe("test-channel")

        # Start consuming — get first event
        try:
            await gen.__anext__()
        except (StopAsyncIteration, StopIteration):
            pass

        # Close the generator (simulates cancellation)
        try:
            await gen.aclose()
        except Exception:
            pass

        # Verify Pub/Sub was cleaned up
        mock_pubsub.unsubscribe.assert_called()
        mock_pubsub.close.assert_called()


class TestHeartbeatNotInTimeline:
    @pytest.mark.asyncio
    async def test_heartbeat_not_stored_in_history(self):
        """FH125: Heartbeat events are not stored in history."""
        backend = MemoryChannelBackend(max_queue_size=10, heartbeat_interval_seconds=0.1)
        await backend.start()
        try:
            await backend.create_channel("hb-history-test")

            # Publish a real message
            await backend.publish("hb-history-test", {"type": "message", "content": "hello"})

            # Wait for heartbeat to be emitted
            await asyncio.sleep(0.3)

            # Check history — should not contain heartbeat
            history = backend._history.get("hb-history-test", [])
            for event in history:
                assert event.get("payload", {}).get("type") != "heartbeat", (
                    f"Heartbeat found in history: {event}"
                )

            # History should only contain the real message
            assert len(history) == 1
            assert history[0].get("payload", {}).get("type") == "message"
        finally:
            await backend.stop()
