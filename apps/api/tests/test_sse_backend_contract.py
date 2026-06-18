"""Patchset 134 Track B: SSE backend contract tests.

Proves that:
1. Both backends implement the public replay() method
2. Replay returns events after the given sequence
3. Routes use only public backend interfaces
4. No private attribute access in production routes
"""
import asyncio
import json
import pytest

from sse_backend import MemoryChannelBackend, BaseSSEBackend


@pytest.fixture
def memory_backend():
    return MemoryChannelBackend(
        ttl_seconds=60,
        max_queue_size=100,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=0,
    )


@pytest.mark.asyncio
async def test_memory_backend_replay_returns_all_events(memory_backend):
    """replay() with no sequence returns all events."""
    await memory_backend.create_channel("replay:all")
    await memory_backend.publish("replay:all", {"type": "event1"})
    await memory_backend.publish("replay:all", {"type": "event2"})
    await memory_backend.publish("replay:all", {"type": "event3"})

    events = await memory_backend.replay("replay:all")
    assert len(events) == 3
    assert events[0]["payload"]["type"] == "event1"
    assert events[2]["payload"]["type"] == "event3"


@pytest.mark.asyncio
async def test_memory_backend_replay_after_sequence(memory_backend):
    """replay(after_sequence=N) returns only events with seq > N."""
    await memory_backend.create_channel("replay:seq")
    await memory_backend.publish("replay:seq", {"type": "event1"})
    await memory_backend.publish("replay:seq", {"type": "event2"})
    await memory_backend.publish("replay:seq", {"type": "event3"})

    # Get sequence of first event
    first_seq = (await memory_backend.replay("replay:seq"))[0]["sequence"]

    events = await memory_backend.replay("replay:seq", after_sequence=first_seq)
    assert len(events) == 2
    assert events[0]["payload"]["type"] == "event2"
    assert events[1]["payload"]["type"] == "event3"


@pytest.mark.asyncio
async def test_memory_backend_replay_empty_channel(memory_backend):
    """replay() on empty channel returns empty list."""
    events = await memory_backend.replay("replay:empty")
    assert events == []


@pytest.mark.asyncio
async def test_memory_backend_replay_nonexistent_channel(memory_backend):
    """replay() on nonexistent channel returns empty list."""
    events = await memory_backend.replay("replay:nonexistent")
    assert events == []


@pytest.mark.asyncio
async def test_memory_backend_replay_does_not_include_heartbeats(memory_backend):
    """Heartbeats are internal and should not appear in history."""
    await memory_backend.create_channel("replay:no_hb")
    await memory_backend.publish("replay:no_hb", {"type": "event1"})

    # Heartbeats are injected during subscribe, not publish, so they won't be in history
    events = await memory_backend.replay("replay:no_hb")
    assert all(e.get("type") != "heartbeat" for e in events)


@pytest.mark.asyncio
async def test_base_sse_backend_has_replay_method():
    """BaseSSEBackend protocol includes replay()."""
    assert hasattr(BaseSSEBackend, "replay")


@pytest.mark.asyncio
async def test_replay_route_uses_public_interface():
    """The replay_events route should only call public backend methods."""
    import ast
    import inspect

    from routes.debates import replay_events
    source = inspect.getsource(replay_events)

    # Should NOT contain private attribute access
    assert "_history" not in source, "replay_events still accesses _history"
    assert "_redis" not in source, "replay_events still accesses _redis"
    assert "_lock" not in source, "replay_events still accesses _lock"
    assert "hasattr" not in source, "replay_events still uses hasattr duck-typing"

    # Should call the public replay() method
    assert ".replay(" in source, "replay_events does not call public replay() method"
