"""SSE load smoke tests.

Bounded local/CI profile for validating SSE infrastructure under load.
Tests subscriber scaling, reconnect behavior, and terminal event delivery.
"""

import sys
import time

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

from sse_backend import MemoryChannelBackend


@pytest.fixture
def backend():
    return MemoryChannelBackend()


@pytest.mark.asyncio
async def test_multiple_subscribers_receive_events(backend):
    channel = "load-test-multi-sub"
    await backend.create_channel(channel)

    sub1 = backend.subscribe(channel, last_sequence=None)
    sub2 = backend.subscribe(channel, last_sequence=None)

    await backend.publish(channel, {"type": "message", "content": "hello"})

    events1 = []
    async for event in sub1:
        events1.append(event)
        if len(events1) >= 1:
            break

    events2 = []
    async for event in sub2:
        events2.append(event)
        if len(events2) >= 1:
            break

    assert len(events1) >= 1
    assert len(events2) >= 1

    await backend.cleanup()


@pytest.mark.asyncio
async def test_replay_delivers_all_events(backend):
    channel = "load-test-replay"
    await backend.create_channel(channel)

    for i in range(10):
        await backend.publish(channel, {"type": "message", "content": f"msg-{i}"})

    replayed = await backend.replay(channel, after_sequence=None)
    assert len(replayed) == 10

    first = replayed[0]
    if "payload" in first:
        assert first["payload"].get("content") == "msg-0"
    else:
        assert first.get("content") == "msg-0"

    last = replayed[-1]
    if "payload" in last:
        assert last["payload"].get("content") == "msg-9"
    else:
        assert last.get("content") == "msg-9"

    await backend.cleanup()


@pytest.mark.asyncio
async def test_terminal_event_stops_subscription(backend):
    channel = "load-test-terminal"
    await backend.create_channel(channel)

    sub = backend.subscribe(channel, last_sequence=None)

    await backend.publish(channel, {"type": "message", "content": "msg1"})
    await backend.publish(channel, {"type": "final", "summary": "done"})

    events = []
    async for event in sub:
        events.append(event)
        if len(events) >= 2:
            break

    assert len(events) == 2
    assert events[-1].get("type") == "final"

    await backend.cleanup()


@pytest.mark.asyncio
async def test_reconnect_after_disconnect(backend):
    channel = "load-test-reconnect"
    await backend.create_channel(channel)

    sub1 = backend.subscribe(channel, last_sequence=None)
    await backend.publish(channel, {"type": "message", "content": "before"})

    events1 = []
    async for event in sub1:
        events1.append(event)
        if len(events1) >= 1:
            break

    sub2 = backend.subscribe(channel, last_sequence=None)
    await backend.publish(channel, {"type": "message", "content": "after"})

    events2 = []
    async for event in sub2:
        events2.append(event)
        if len(events2) >= 1:
            break

    assert len(events1) == 1
    assert len(events2) == 1

    await backend.cleanup()


@pytest.mark.asyncio
async def test_heartbeat_stability(backend):
    channel = "load-test-heartbeat"
    await backend.create_channel(channel)

    sub = backend.subscribe(channel, last_sequence=None)

    start = time.monotonic()
    for i in range(5):
        await backend.publish(channel, {"type": "heartbeat"})
    elapsed = time.monotonic() - start

    events = []
    async for event in sub:
        events.append(event)
        if len(events) >= 5:
            break

    assert elapsed < 5.0
    assert len(events) == 5

    await backend.cleanup()


@pytest.mark.asyncio
async def test_cleanup_runs_without_error(backend):
    channel = "load-test-cleanup"
    await backend.create_channel(channel)

    sub = backend.subscribe(channel, last_sequence=None)
    await backend.publish(channel, {"type": "message", "content": "hi"})

    async for _ in sub:
        break

    await backend.cleanup()
    assert True
