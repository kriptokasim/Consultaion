"""SSE heartbeat delivery and backpressure tests.

Patchset 133 §7.3: Proves heartbeat reaches browser, is not in timeline,
and terminal events cannot be dropped.
"""

import asyncio

import pytest
from sse_backend import MemoryChannelBackend


@pytest.fixture
def backend():
    return MemoryChannelBackend(
        max_queue_size=10,
        heartbeat_interval_seconds=0.1,
        idle_timeout_seconds=10,
    )


class TestHeartbeatDelivery:
    @pytest.mark.asyncio
    async def test_heartbeat_reaches_subscriber(self, backend):
        """FH125: Heartbeat events are delivered to subscribers."""
        await backend.start()
        try:
            await backend.create_channel("test-hb")
            events = []
            async for event in backend.subscribe("test-hb", last_sequence=0):
                events.append(event)
                if len(events) >= 2:
                    break

            heartbeat_events = [e for e in events if e.get("payload", {}).get("type") == "heartbeat"]
            assert len(heartbeat_events) > 0, "No heartbeat events received"
        finally:
            await backend.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_not_in_history(self, backend):
        """FH125: Heartbeat events are not stored in history."""
        await backend.start()
        try:
            await backend.create_channel("test-hb-history")
            await backend.publish("test-hb-history", {"type": "message", "content": "hello"})

            # Wait for heartbeat
            await asyncio.sleep(0.2)

            # Check history — should not contain heartbeat
            history = backend._history.get("test-hb-history", [])
            for event in history:
                assert event.get("payload", {}).get("type") != "heartbeat", (
                    "Heartbeat found in history"
                )
        finally:
            await backend.stop()


class TestTerminalDelivery:
    @pytest.mark.asyncio
    async def test_terminal_event_always_delivered(self, backend):
        """FH125: Terminal events are delivered even under backpressure."""
        await backend.start()
        try:
            await backend.create_channel("test-terminal")
            subscriber = asyncio.Queue(maxsize=10)
            async with backend._lock:
                backend._subscribers.setdefault("test-terminal", []).append(subscriber)

            # Fill the queue to capacity
            for i in range(10):
                await backend.publish("test-terminal", {"type": f"fill-{i}"})

            # Terminal event should still be deliverable
            await backend.publish("test-terminal", {"type": "final"})

            # Drain and check
            events = []
            while not subscriber.empty():
                events.append(subscriber.get_nowait())

            terminal_events = [e for e in events if e.get("payload", {}).get("type") == "final"]
            assert len(terminal_events) > 0, "Terminal event was dropped under backpressure"
        finally:
            await backend.stop()


class TestLeaseCleanup:
    @pytest.mark.asyncio
    async def test_lease_released_on_disconnect(self, backend):
        """FH125: Lease is released when subscriber disconnects."""
        from sse_backend import StreamLeaseManager

        manager = StreamLeaseManager(max_streams=5, lease_ttl=60)

        # Acquire lease
        result = await manager.try_acquire("debate-1", "sub-1", "user-1")
        assert result.value == "acquired"

        count = await manager.active_count("debate-1")
        assert count == 1

        # Release lease
        await manager.release("debate-1", "sub-1", "user-1")

        # Count should be 0 (memory cleanup is instant)
        count = await manager.active_count("debate-1")
        assert count == 0
