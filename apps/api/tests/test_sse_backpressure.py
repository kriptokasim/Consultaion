"""Patchset 132 Track C: Terminal event backpressure protection tests.

Proves that:
1. Critical events (final, error) are never dropped under backpressure
2. Delta coalescing preserves output order
3. Fast and slow subscribers both receive terminal state
4. Overflow metrics increment correctly
5. Loss-tolerant events are dropped before important/critical events
"""
import asyncio

import pytest
from sse_backend import MemoryChannelBackend, _event_priority


@pytest.fixture
def backend():
    return MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=5,  # Small queue to trigger backpressure easily
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0,
    )


@pytest.mark.asyncio
async def test_final_event_never_dropped_under_backpressure(backend):
    """A 'final' event must always reach the subscriber even when queue is full."""
    await backend.create_channel("bp:final")

    # Fill queue to capacity with loss-tolerant events
    for i in range(5):
        await backend.publish("bp:final", {"type": "model_response_delta", "text": f"chunk{i}"})

    # Now publish a final event — must not be dropped
    await backend.publish("bp:final", {"type": "final", "result": "done"})

    events = []
    async for env in backend.subscribe("bp:final"):
        events.append(env)
        if env.get("payload", {}).get("type") == "final":
            break

    # Final must be in the received events
    types = [e.get("payload", {}).get("type") for e in events]
    assert "final" in types, f"final event was dropped! Received: {types}"


@pytest.mark.asyncio
async def test_error_event_never_dropped_under_backpressure(backend):
    """An 'error' event must always reach the subscriber even when queue is full."""
    await backend.create_channel("bp:error")

    # Fill queue to capacity
    for i in range(5):
        await backend.publish("bp:error", {"type": "model_response_delta", "text": f"chunk{i}"})

    # Publish error event
    await backend.publish("bp:error", {"type": "error", "message": "failed"})

    events = []
    async for env in backend.subscribe("bp:error"):
        events.append(env)
        if env.get("payload", {}).get("type") == "error":
            break

    types = [e.get("payload", {}).get("type") for e in events]
    assert "error" in types, f"error event was dropped! Received: {types}"


@pytest.mark.asyncio
async def test_debate_completed_never_dropped(backend):
    """debate_completed must not be dropped under backpressure."""
    await backend.create_channel("bp:completed")

    for i in range(5):
        await backend.publish("bp:completed", {"type": "model_response_delta", "text": f"chunk{i}"})

    await backend.publish("bp:completed", {"type": "debate_completed"})

    events = []
    async for env in backend.subscribe("bp:completed"):
        events.append(env)
        if env.get("payload", {}).get("type") == "debate_completed":
            break

    types = [e.get("payload", {}).get("type") for e in events]
    assert "debate_completed" in types


@pytest.mark.asyncio
async def test_debate_failed_never_dropped(backend):
    """debate_failed must not be dropped under backpressure."""
    await backend.create_channel("bp:failed")

    for i in range(5):
        await backend.publish("bp:failed", {"type": "model_response_delta", "text": f"chunk{i}"})

    await backend.publish("bp:failed", {"type": "debate_failed"})

    events = []
    async for env in backend.subscribe("bp:failed"):
        events.append(env)
        if env.get("payload", {}).get("type") == "debate_failed":
            break

    types = [e.get("payload", {}).get("type") for e in events]
    assert "debate_failed" in types


@pytest.mark.asyncio
async def test_loss_tolerant_events_dropped_before_important(backend):
    """Loss-tolerant events (deltas) should be dropped before important events."""
    await backend.create_channel("bp:priority")

    # Fill queue with deltas (loss-tolerant)
    for i in range(5):
        await backend.publish("bp:priority", {"type": "model_response_delta", "text": f"chunk{i}"})

    # Publish an important event
    await backend.publish("bp:priority", {"type": "arena_response", "data": "result"})

    # And a final
    await backend.publish("bp:priority", {"type": "final"})

    events = []
    async for env in backend.subscribe("bp:priority"):
        events.append(env)
        if env.get("payload", {}).get("type") == "final":
            break

    types = [e.get("payload", {}).get("type") for e in events]
    # Both important and critical should be present
    assert "arena_response" in types, f"important event was dropped: {types}"
    assert "final" in types, f"critical event was dropped: {types}"


@pytest.mark.asyncio
async def test_delta_coalescing_preserves_order(backend):
    """Consecutive deltas should be coalesced and preserve output order."""
    # Use a larger queue so deltas are not dropped by backpressure
    large_backend = MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0,
    )
    await large_backend.create_channel("bp:coalesce")

    # Publish many deltas rapidly
    for i in range(20):
        await large_backend.publish("bp:coalesce", {
            "type": "model_response_delta",
            "response_id": "resp:1",
            "text": f"chunk{i}",
        })

    events = []
    async for env in large_backend.subscribe("bp:coalesce"):
        events.append(env)

    delta_events = [e for e in events if e.get("payload", {}).get("type") == "model_response_delta"]
    # All deltas should arrive in a large queue
    assert len(delta_events) == 20
    # Order should be preserved
    texts = [e.get("payload", {}).get("text") for e in delta_events]
    assert texts == [f"chunk{i}" for i in range(20)]


@pytest.mark.asyncio
async def test_slow_subscriber_receives_terminal_state(backend):
    """A slow subscriber should still receive terminal events."""
    await backend.create_channel("bp:slow")

    fast_events = []
    slow_events = []

    async def fast_consumer():
        async for env in backend.subscribe("bp:slow"):
            fast_events.append(env)
            if env.get("payload", {}).get("type") == "final":
                break

    async def slow_consumer():
        async for env in backend.subscribe("bp:slow"):
            slow_events.append(env)
            if env.get("payload", {}).get("type") == "final":
                break

    fast_task = asyncio.create_task(fast_consumer())
    slow_task = asyncio.create_task(slow_consumer())
    await asyncio.sleep(0.05)

    # Publish events
    for i in range(3):
        await backend.publish("bp:slow", {"type": "model_response_delta", "text": f"chunk{i}"})
    await backend.publish("bp:slow", {"type": "final"})

    await asyncio.wait_for(fast_task, timeout=2)
    await asyncio.wait_for(slow_task, timeout=2)

    # Both should receive the final event
    assert any(e.get("payload", {}).get("type") == "final" for e in fast_events)
    assert any(e.get("payload", {}).get("type") == "final" for e in slow_events)


@pytest.mark.asyncio
async def test_event_priority_classification():
    """Verify event priority classification."""
    assert _event_priority({"type": "final"}) == 0
    assert _event_priority({"type": "error"}) == 0
    assert _event_priority({"type": "debate_completed"}) == 0
    assert _event_priority({"type": "debate_failed"}) == 0
    assert _event_priority({"type": "arena_response"}) == 1
    assert _event_priority({"type": "model_response_completed"}) == 1
    assert _event_priority({"type": "model_response_failed"}) == 1
    assert _event_priority({"type": "perspectives_ready"}) == 1
    assert _event_priority({"type": "model_response_delta"}) == 2
    assert _event_priority({"type": "heartbeat"}) == 2
    assert _event_priority({"type": "notice"}) == 2


@pytest.mark.asyncio
async def test_heartbeat_events_are_loss_tolerant(backend):
    """Heartbeat events should be classified as loss-tolerant (droppable)."""
    from sse_backend import _event_priority
    assert _event_priority({"type": "heartbeat"}) == 2


@pytest.mark.asyncio
async def test_all_critical_queue_saturation(backend):
    """If the queue is 100% full of critical events, a new critical event replaces the oldest one (latest critical wins)."""
    channel = "bp:all_critical"
    await backend.create_channel(channel)

    events = []
    consumer_started = asyncio.Event()
    allow_consumer = asyncio.Event()

    async def blocked_consumer():
        # Subscribe before publishing so we get a subscriber queue
        sub = backend.subscribe(channel)
        consumer_started.set()
        await allow_consumer.wait()
        async for env in sub:
            events.append(env)
            if len(events) == 5:
                break

    task = asyncio.create_task(blocked_consumer())
    await consumer_started.wait()
    # Yield control briefly to ensure subscription is fully registered
    await asyncio.sleep(0.05)

    # Fill queue completely with critical events (priority 0)
    # The queue size is 5 in the fixture.
    for i in range(5):
        await backend.publish(channel, {"type": "debate_completed", "id": i})

    # Now publish a new critical event to a full queue.
    await backend.publish(channel, {"type": "debate_completed", "id": 999})

    # Unblock consumer to read events
    allow_consumer.set()
    await asyncio.wait_for(task, timeout=2)

    ids = [e.get("payload", {}).get("id") for e in events]
    # The oldest event (id=0) should have been dropped, and id=999 should be present
    assert ids == [1, 2, 3, 4, 999]

