"""Tests for SSE memory backend broadcast semantics.

FH125: Verifies per-subscriber queue fan-out, event replay,
terminal event handling, and subscriber cleanup.
"""
import asyncio
import pytest
import time

from sse_backend import MemoryChannelBackend


@pytest.fixture
def backend():
    return MemoryChannelBackend(ttl_seconds=60, max_queue_size=100, idle_timeout_seconds=10)


@pytest.mark.asyncio
async def test_single_subscriber_receives_events(backend):
    await backend.create_channel("test:1")

    events = []

    async def consumer():
        async for env in backend.subscribe("test:1"):
            events.append(env)
            if len(events) >= 3:
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    await backend.publish("test:1", {"type": "notice", "msg": "a"})
    await backend.publish("test:1", {"type": "notice", "msg": "b"})
    await backend.publish("test:1", {"type": "final", "msg": "done"})

    await asyncio.wait_for(task, timeout=2)
    assert len(events) == 3
    assert events[0]["payload"]["msg"] == "a"
    assert events[2]["payload"]["type"] == "final"


@pytest.mark.asyncio
async def test_two_subscribers_receive_identical_events(backend):
    await backend.create_channel("test:2")

    events_a = []
    events_b = []

    async def consumer_a():
        async for env in backend.subscribe("test:2"):
            events_a.append(env)
            if len(events_a) >= 3:
                break

    async def consumer_b():
        async for env in backend.subscribe("test:2"):
            events_b.append(env)
            if len(events_b) >= 3:
                break

    task_a = asyncio.create_task(consumer_a())
    task_b = asyncio.create_task(consumer_b())
    await asyncio.sleep(0.05)

    await backend.publish("test:2", {"type": "notice", "msg": "x"})
    await backend.publish("test:2", {"type": "notice", "msg": "y"})
    await backend.publish("test:2", {"type": "final", "msg": "end"})

    await asyncio.wait_for(task_a, timeout=2)
    await asyncio.wait_for(task_b, timeout=2)

    assert len(events_a) == 3
    assert len(events_b) == 3
    # Both subscribers should receive the same sequence
    for i in range(3):
        assert events_a[i]["sequence"] == events_b[i]["sequence"]


@pytest.mark.asyncio
async def test_replay_history_on_resubscribe(backend):
    await backend.create_channel("test:3")

    await backend.publish("test:3", {"type": "notice", "msg": "before"})
    await backend.publish("test:3", {"type": "notice", "msg": "middle"})

    events = []

    async def consumer():
        async for env in backend.subscribe("test:3", last_sequence=0):
            events.append(env)
            if len(events) >= 3:
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    await backend.publish("test:3", {"type": "final", "msg": "after"})

    await asyncio.wait_for(task, timeout=2)
    assert len(events) >= 2
    # Should have replayed events with sequence > 0
    assert events[0]["sequence"] > 0


@pytest.mark.asyncio
async def test_terminal_event_closes_stream(backend):
    await backend.create_channel("test:4")

    events = []

    async def consumer():
        async for env in backend.subscribe("test:4"):
            events.append(env)

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    await backend.publish("test:4", {"type": "notice", "msg": "hi"})
    await backend.publish("test:4", {"type": "error", "msg": "fail"})

    await asyncio.wait_for(task, timeout=2)
    assert len(events) == 2
    assert events[1]["payload"]["type"] == "error"


@pytest.mark.asyncio
async def test_subscriber_removed_on_disconnect(backend):
    await backend.create_channel("test:5")

    async def consumer():
        count = 0
        async for env in backend.subscribe("test:5"):
            count += 1
            if count >= 1:
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    await backend.publish("test:5", {"type": "notice", "msg": "a"})
    await asyncio.wait_for(task, timeout=2)

    await asyncio.sleep(0.1)
    # After consumer finishes, subscriber queue should be removed
    assert len(backend._subscribers.get("test:5", [])) == 0


@pytest.mark.asyncio
async def test_publish_before_subscription_replays_history(backend):
    await backend.create_channel("test:6")

    await backend.publish("test:6", {"type": "notice", "msg": "historical"})

    events = []

    async def consumer():
        async for env in backend.subscribe("test:6"):
            events.append(env)
            if len(events) >= 1:
                break

    task = asyncio.create_task(consumer())
    await asyncio.wait_for(task, timeout=2)

    assert len(events) == 1
    assert events[0]["payload"]["msg"] == "historical"
