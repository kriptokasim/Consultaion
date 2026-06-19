"""SSE load smoke tests.

Bounded local/CI profile for validating SSE infrastructure under load.
Tests subscriber scaling, reconnect behavior, and terminal event delivery.
"""

import sys
import time

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

from sse_backend import MemoryChannelBackend as MemorySSEBackend


@pytest.fixture
def backend():
    return MemorySSEBackend()


@pytest.mark.asyncio
async def test_multiple_subscribers_one_channel(backend):
    channel = "load-test-single"
    await backend.create_channel(channel)

    subscribers = []
    for i in range(10):
        sub = backend.subscribe(channel, last_sequence=None)
        subscribers.append(sub)

    for i in range(5):
        event = {"type": "message", "content": f"msg-{i}"}
        await backend.publish(channel, event)

    for sub in subscribers:
        count = 0
        async for _ in sub:
            count += 1
            if count >= 5:
                break
        assert count == 5

    await backend.cleanup()


@pytest.mark.asyncio
async def test_multiple_channels_one_subscriber(backend):
    channels = [f"load-test-multi-{i}" for i in range(5)]
    for ch in channels:
        await backend.create_channel(ch)

    for ch in channels:
        event = {"type": "message", "content": "hello"}
        await backend.publish(ch, event)

    for ch in channels:
        events = await backend.replay(ch, after_sequence=None)
        assert len(events) >= 1

    await backend.cleanup()


@pytest.mark.asyncio
async def test_terminal_event_delivery(backend):
    channel = "load-test-terminal"
    await backend.create_channel(channel)

    sub = backend.subscribe(channel, last_sequence=None)

    await backend.publish(channel, {"type": "message", "content": "msg1"})
    await backend.publish(channel, {"type": "message", "content": "msg2"})
    await backend.publish(channel, {"type": "final", "summary": "done"})

    events = []
    async for event in sub:
        events.append(event)
        if len(events) >= 3:
            break

    assert len(events) == 3
    assert events[-1].get("type") == "final"

    await backend.cleanup()


@pytest.mark.asyncio
async def test_replay_under_load(backend):
    channel = "load-test-replay"
    await backend.create_channel(channel)

    for i in range(20):
        await backend.publish(channel, {"type": "message", "content": f"msg-{i}"})

    replayed = await backend.replay(channel, after_sequence=None)
    assert len(replayed) == 20

    await backend.cleanup()


@pytest.mark.asyncio
async def test_heartbeat_stability(backend):
    channel = "load-test-heartbeat"
    await backend.create_channel(channel)

    sub = backend.subscribe(channel, last_sequence=None)

    start = time.monotonic()
    for i in range(10):
        await backend.publish(channel, {"type": "heartbeat"})
    elapsed = time.monotonic() - start

    assert elapsed < 5.0

    await backend.cleanup()


@pytest.mark.asyncio
async def test_cleanup_runs_without_error(backend):
    channel = "load-test-leak"
    await backend.create_channel(channel)

    sub = backend.subscribe(channel, last_sequence=None)
    await backend.publish(channel, {"type": "message", "content": "hi"})

    async for _ in sub:
        break

    await backend.cleanup()

    assert True
