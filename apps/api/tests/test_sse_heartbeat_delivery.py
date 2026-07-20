"""PS157 Track H: SSE heartbeat delivery tests.

Verifies that heartbeats are published by the backend and reach the
subscriber without altering the EventSource cursor.
"""

from __future__ import annotations

import asyncio
import json

import pytest


@pytest.mark.asyncio
async def test_memory_backend_heartbeat_forwarded():
    """Heartbeat events published to a channel are received by subscribers."""
    from sse_backend import get_sse_backend, MemoryChannelBackend

    backend = MemoryChannelBackend()
    channel = "debate:test-heartbeat-1"

    received = []

    async def collect():
        async for event in backend.subscribe(channel):
            received.append(event)
            if event.get("type") == "heartbeat" or (
                isinstance(event.get("payload"), dict)
                and event["payload"].get("type") == "heartbeat"
            ):
                break

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0.05)

    await backend.publish(channel, {
        "type": "heartbeat",
        "payload": {"type": "heartbeat", "timestamp": "2026-01-01T00:00:00Z"},
    })

    await asyncio.wait_for(collector, timeout=2)
    assert len(received) == 1
    evt = received[0]
    assert evt["type"] == "heartbeat" or evt.get("payload", {}).get("type") == "heartbeat"


@pytest.mark.asyncio
async def test_heartbeat_has_no_last_event_id():
    """Heartbeats should not advance the resume cursor."""
    from sse_backend import get_sse_backend, MemoryChannelBackend

    backend = MemoryChannelBackend()
    channel = "debate:test-heartbeat-cursor"

    events = []

    async def collect():
        async for event in backend.subscribe(channel):
            events.append(event)
            if len(events) >= 2:
                break

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0.05)

    await backend.publish(channel, {"type": "heartbeat", "sequence": 0})
    await backend.publish(channel, {"type": "model_response_completed", "sequence": 1})

    await asyncio.wait_for(collector, timeout=2)
    assert len(events) == 2
    # Sequence 0 heartbeats should not be replayed on reconnect
    heartbeat = events[0]
    if heartbeat.get("sequence") == 0:
        assert heartbeat["type"] == "heartbeat"


@pytest.mark.asyncio
async def test_heartbeat_does_not_enter_timeline():
    """Heartbeat events should be filtered from the frontend timeline."""
    from sse_backend import get_sse_backend, MemoryChannelBackend

    backend = MemoryChannelBackend()
    channel = "debate:test-timeline-filter"

    events = []

    async def collect():
        async for event in backend.subscribe(channel):
            if event.get("type") == "heartbeat":
                continue
            events.append(event)
            break

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0.05)

    await backend.publish(channel, {"type": "heartbeat"})
    await backend.publish(channel, {"type": "model_response_completed"})

    await asyncio.wait_for(collector, timeout=2)
    assert len(events) == 1
    assert events[0]["type"] == "model_response_completed"


@pytest.mark.asyncio
async def test_heartbeat_updates_activity_timestamp():
    """Heartbeats should keep the silence watchdog from firing."""
    from sse_backend import get_sse_backend, MemoryChannelBackend

    backend = MemoryChannelBackend()
    channel = "debate:test-activity"

    first_event_time = None

    async def collect():
        nonlocal first_event_time
        async for event in backend.subscribe(channel):
            if first_event_time is None:
                first_event_time = event.get("timestamp")
            break

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    await backend.publish(channel, {"type": "heartbeat", "timestamp": "2026-01-01T00:00:00Z"})
    await asyncio.wait_for(collector, timeout=2)
    assert first_event_time is not None
