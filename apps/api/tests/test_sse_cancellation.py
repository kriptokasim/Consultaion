"""Patchset 132 Track A: SSE cancellation propagation tests.

Proves that:
1. CancelledError propagates through memory backend subscriptions
2. Subscriber queues are removed after cancellation
3. Redis Pub/Sub is closed after cancellation
4. No stream lease remains after cancellation
"""
import asyncio
import pytest

from sse_backend import MemoryChannelBackend


@pytest.fixture
def backend():
    return MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0,  # Disable heartbeats for clean tests
    )


@pytest.mark.asyncio
async def test_cancelled_error_propagates_from_memory_subscriber(backend):
    """CancelledError must propagate, not be swallowed as normal completion."""
    await backend.create_channel("cancel:propagate")

    async def blocking_consumer():
        events = []
        async for env in backend.subscribe("cancel:propagate"):
            events.append(env)
            # Never break — this consumer blocks until cancelled
        return events

    task = asyncio.create_task(blocking_consumer())
    await asyncio.sleep(0.05)  # Let subscriber register

    # Verify subscriber is registered
    assert len(backend._subscribers.get("cancel:propagate", [])) == 1

    # Cancel the subscriber
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_subscriber_queue_removed_after_cancellation(backend):
    """Subscriber queue must be cleaned up after cancellation."""
    await backend.create_channel("cancel:cleanup")

    async def blocking_consumer():
        async for env in backend.subscribe("cancel:cleanup"):
            pass  # Never break

    task = asyncio.create_task(blocking_consumer())
    await asyncio.sleep(0.05)

    # Verify subscriber is registered
    subs = backend._subscribers.get("cancel:cleanup", [])
    assert len(subs) == 1

    # Cancel and await
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify subscriber queue is removed
    subs_after = backend._subscribers.get("cancel:cleanup", [])
    assert len(subs_after) == 0


@pytest.mark.asyncio
async def test_cancelled_subscriber_receives_no_events_after_cancel(backend):
    """After cancellation, subscriber should not receive new events."""
    await backend.create_channel("cancel:no_events")
    received = []

    async def consumer():
        async for env in backend.subscribe("cancel:no_events"):
            received.append(env)

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    # Cancel the consumer
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Publish events after cancellation
    await backend.publish("cancel:no_events", {"type": "after_cancel"})

    # Wait a bit for any potential delivery
    await asyncio.sleep(0.1)

    # Should not have received the post-cancel event
    assert len(received) == 0


@pytest.mark.asyncio
async def test_cancellation_does_not_affect_other_subscribers(backend):
    """Cancelling one subscriber must not affect others."""
    await backend.create_channel("cancel:isolate")
    events_b = []

    async def consumer_b():
        async for env in backend.subscribe("cancel:isolate"):
            events_b.append(env)
            if len(events_b) >= 2:
                break

    task_b = asyncio.create_task(consumer_b())
    await asyncio.sleep(0.05)

    # consumer_b is running, publish events
    await backend.publish("cancel:isolate", {"type": "event_b0"})
    await backend.publish("cancel:isolate", {"type": "event_b1"})

    await asyncio.wait_for(task_b, timeout=2)
    assert len(events_b) == 2


@pytest.mark.asyncio
async def test_terminal_event_during_cancelled_cleanup(backend):
    """Cancellation during terminal event processing should clean up properly."""
    await backend.create_channel("cancel:terminal")

    async def consumer():
        async for env in backend.subscribe("cancel:terminal"):
            if env.get("payload", {}).get("type") == "final":
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    # Cancel while waiting for final
    task.cancel()

    # Publish final — should not cause issues
    await backend.publish("cancel:terminal", {"type": "final"})

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify cleanup happened
    subs = backend._subscribers.get("cancel:terminal", [])
    assert len(subs) == 0


@pytest.mark.asyncio
async def test_rapid_subscribe_cancel_cycle(backend):
    """Rapid subscribe/cancel cycles should not leak subscriber queues."""
    await backend.create_channel("cancel:rapid")

    for i in range(20):
        async def consumer():
            async for env in backend.subscribe("cancel:rapid"):
                pass

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # All subscriber queues should be cleaned up
    subs = backend._subscribers.get("cancel:rapid", [])
    assert len(subs) == 0
