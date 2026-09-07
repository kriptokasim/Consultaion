"""The Redis pubsub connection must be released on every exit path.

A subscribed Redis connection is dedicated -- it cannot serve any other command
for as long as it is subscribed. The old subscribe() acquired one at the top but
only guarded it from step 5 onward, leaving subscribe/history-read/replay/drain
unprotected. A client that disconnected during replay (routine on mobile, where
the reconnect ladder fires constantly) abandoned the generator at a yield and
leaked the connection for the life of the process.

On Redis Cloud Essentials 30MB the database allows 30 concurrent connections, so
a single debate with a handful of reconnects exhausted it. The async pool ceiling
was 50 -- above the plan's own limit -- so the pool never pushed back; it just
kept opening until Redis refused.
"""
from __future__ import annotations

import json

import pytest

# Step 5 blocks forever when no message ever arrives, which is correct for a live
# stream and fatal for a test. Every case here either ends on a terminal event or
# is closed explicitly, and the timeout turns a regression into a fast failure
# instead of a hung suite.
pytestmark = [pytest.mark.anyio, pytest.mark.timeout(10)]


class FakePubSub:
    """Records subscribe/close so a leak is observable."""

    def __init__(self, messages=None):
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.closed = False
        self._messages = list(messages or [])

    async def subscribe(self, channel_id):
        self.subscribed.append(channel_id)

    async def unsubscribe(self, channel_id):
        self.unsubscribed.append(channel_id)

    async def close(self):
        self.closed = True

    async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        return self._messages.pop(0) if self._messages else None


class FakeRedis:
    def __init__(self, history=None, pubsub=None, lrange_error=None):
        self._history = history or []
        self._pubsub = pubsub or FakePubSub()
        self._lrange_error = lrange_error

    def pubsub(self):
        return self._pubsub

    async def lrange(self, key, start, end):
        if self._lrange_error:
            raise self._lrange_error
        return self._history


def _backend(redis_stub):
    from sse_backend import RedisChannelBackend

    backend = RedisChannelBackend.__new__(RedisChannelBackend)
    backend._redis = redis_stub
    backend._heartbeat_interval_seconds = 0
    return backend


async def test_connection_released_when_client_aborts_during_replay():
    """The exact leak: abandon the generator mid-replay, before step 5."""
    history = [json.dumps({"sequence": i, "payload": {"type": "delta"}}) for i in range(5)]
    pubsub = FakePubSub()
    backend = _backend(FakeRedis(history=history, pubsub=pubsub))

    agen = backend.subscribe("chan-1")
    await agen.__anext__()          # consume one replayed event, then walk away
    await agen.aclose()             # what an SSE client disconnect looks like

    assert pubsub.closed, "pubsub connection leaked when the client aborted during replay"
    assert pubsub.unsubscribed == ["chan-1"]


async def test_connection_released_on_terminal_event_during_replay():
    history = [json.dumps({"sequence": 1, "payload": {"type": "final"}})]
    pubsub = FakePubSub()
    backend = _backend(FakeRedis(history=history, pubsub=pubsub))

    events = [evt async for evt in backend.subscribe("chan-2")]

    assert len(events) == 1
    assert pubsub.closed
    assert pubsub.unsubscribed == ["chan-2"]


async def test_connection_released_when_history_read_raises():
    """lrange failing must not strand the already-subscribed connection.

    The history read swallows its own exception and carries on with an empty
    replay, so the stream continues to live consumption -- the connection is
    still held, and still has to be released when the stream ends.
    """
    pubsub = FakePubSub([{"data": json.dumps({"sequence": 1, "payload": {"type": "final"}})}])
    backend = _backend(FakeRedis(pubsub=pubsub, lrange_error=RuntimeError("redis down")))

    events = [evt async for evt in backend.subscribe("chan-3")]

    assert len(events) == 1
    assert pubsub.closed


async def test_release_is_not_defeated_by_a_failing_unsubscribe():
    """close() must still run if unsubscribe() throws -- that is the connection."""
    class AngryPubSub(FakePubSub):
        async def unsubscribe(self, channel_id):
            raise RuntimeError("connection already gone")

    pubsub = AngryPubSub([])
    backend = _backend(
        FakeRedis(history=[json.dumps({"sequence": 1, "payload": {"type": "final"}})], pubsub=pubsub)
    )

    [evt async for evt in backend.subscribe("chan-4")]

    assert pubsub.closed, "a failing unsubscribe must not skip close()"


def test_pool_ceilings_fit_the_smallest_managed_plan():
    """Guards the misconfiguration, not just the leak.

    Redis Cloud Essentials 30MB allows 30 concurrent connections per database,
    and every process opens its own pools. Ceilings summing above the plan mean
    the pool never applies backpressure -- it opens until Redis refuses.
    """
    from config import settings

    total = settings.REDIS_MAX_CONNECTIONS_SYNC + settings.REDIS_MAX_CONNECTIONS_ASYNC
    assert total <= 25, (
        f"per-process Redis budget is {total}; leave headroom under the 30-connection "
        "plan cap for a second process and ad-hoc clients"
    )
