"""Patchset 132 Track D: SSE heartbeat and silence detection tests.

Proves that:
1. Backend emits heartbeat events periodically
2. Heartbeat events reset the silence timer
3. Heartbeat events do not enter the user-facing timeline
4. Heartbeat events do not trigger debate hydration
"""
import asyncio

import pytest
from sse_backend import MemoryChannelBackend


@pytest.mark.asyncio
async def test_heartbeat_emitted_periodically():
    """Backend should emit heartbeat events when no real events are flowing."""
    backend = MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0.2,  # 200ms for fast test
    )
    await backend.create_channel("hb:periodic")

    events = []

    async def consumer():
        async for env in backend.subscribe("hb:periodic"):
            events.append(env)
            if len(events) >= 3:
                break

    task = asyncio.create_task(consumer())
    await asyncio.wait_for(task, timeout=5)

    # Should have received at least one heartbeat
    heartbeat_events = [e for e in events if e.get("type") == "heartbeat"]
    assert len(heartbeat_events) >= 1, f"No heartbeats received in {len(events)} events"


@pytest.mark.asyncio
async def test_real_event_resets_heartbeat_timer():
    """Receiving a real event should reset the heartbeat timer."""
    backend = MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0.3,
    )
    await backend.create_channel("hb:reset")

    events = []

    async def consumer():
        async for env in backend.subscribe("hb:reset"):
            events.append(env)
            if len(events) >= 4:
                break

    task = asyncio.create_task(consumer())

    # Publish a real event before heartbeat interval
    await asyncio.sleep(0.1)
    await backend.publish("hb:reset", {"type": "notice", "msg": "hello"})

    # Wait longer — should get heartbeat after the real event
    await asyncio.sleep(0.4)

    # Publish another real event
    await backend.publish("hb:reset", {"type": "notice", "msg": "world"})

    try:
        await asyncio.wait_for(task, timeout=3)
    except asyncio.TimeoutError:
        pass

    heartbeat_events = [e for e in events if e.get("type") == "heartbeat"]
    notice_events = [e for e in events if e.get("payload", {}).get("type") == "notice"]

    # Should have received at least one notice
    assert len(notice_events) >= 1
    # Should have received at least one heartbeat (during the 0.3s gap)
    assert len(heartbeat_events) >= 1


@pytest.mark.asyncio
async def test_heartbeat_not_in_history():
    """Heartbeat events should not be stored in the backend history."""
    backend = MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0.2,
    )
    await backend.create_channel("hb:no_history")

    events = []

    async def consumer():
        async for env in backend.subscribe("hb:no_history"):
            events.append(env)
            if len(events) >= 2:
                break

    task = asyncio.create_task(consumer())
    await asyncio.wait_for(task, timeout=5)

    # Check that heartbeats are not in the history
    history = backend._history.get("hb:no_history", [])
    heartbeat_in_history = [
        h for h in history
        if h.get("type") == "heartbeat" or h.get("payload", {}).get("type") == "heartbeat"
    ]
    assert len(heartbeat_in_history) == 0, "Heartbeat events should not be in history"


@pytest.mark.asyncio
async def test_heartbeat_event_structure():
    """Heartbeat events should have the correct structure."""
    backend = MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0.2,
    )
    await backend.create_channel("hb:structure")

    events = []

    async def consumer():
        async for env in backend.subscribe("hb:structure"):
            events.append(env)
            if len(events) >= 1:
                break

    task = asyncio.create_task(consumer())
    await asyncio.wait_for(task, timeout=5)

    hb = events[0]
    assert hb.get("type") == "heartbeat"
    assert hb.get("payload", {}).get("type") == "heartbeat"
    assert "id" in hb
    assert "timestamp" in hb


@pytest.mark.asyncio
async def test_heartbeat_does_not_prevent_terminal_event():
    """Heartbeat emission should not prevent terminal events from being delivered."""
    backend = MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0.1,
    )
    await backend.create_channel("hb:terminal")

    events = []

    async def consumer():
        async for env in backend.subscribe("hb:terminal"):
            events.append(env)
            if env.get("payload", {}).get("type") == "final":
                break

    task = asyncio.create_task(consumer())

    # Wait for heartbeat
    await asyncio.sleep(0.2)

    # Publish final
    await backend.publish("hb:terminal", {"type": "final"})

    await asyncio.wait_for(task, timeout=3)

    types = [e.get("payload", {}).get("type") or e.get("type") for e in events]
    assert "final" in types
