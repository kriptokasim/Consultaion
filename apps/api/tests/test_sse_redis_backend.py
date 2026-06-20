"""Redis SSE backend integration tests.

FH125 Track C: Tests that exercise the real RedisChannelBackend against
a live Redis instance. These tests MUST fail if Redis is unavailable.
"""
import asyncio
import os

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

# Require real Redis — skip if not configured
REDIS_URL = os.environ.get("REDIS_URL", "")
if not REDIS_URL:
    pytest.skip("REDIS_URL not set — skipping Redis SSE tests", allow_module_level=True)

from sse_backend import RedisChannelBackend


@pytest_asyncio.fixture
async def redis_client():
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def backend(redis_client):
    # Flush test keys before each test
    keys = await redis_client.keys("sse:test_redis:*")
    if keys:
        await redis_client.delete(*keys)

    b = RedisChannelBackend(url=REDIS_URL, ttl_seconds=60, max_queue_size=100)
    # Override the redis client with our test client
    b._redis = redis_client
    yield b


@pytest.mark.asyncio
async def test_redis_single_subscriber_receives_events(backend):
    channel_id = "test_redis:single"
    await backend.create_channel(channel_id)

    events = []

    async def consumer():
        async for env in backend.subscribe(channel_id):
            events.append(env)
            if len(events) >= 3:
                break

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.1)

    await backend.publish(channel_id, {"type": "notice", "msg": "a"})
    await backend.publish(channel_id, {"type": "notice", "msg": "b"})
    await backend.publish(channel_id, {"type": "final", "msg": "done"})

    await asyncio.wait_for(task, timeout=5)
    assert len(events) == 3
    assert events[0]["payload"]["msg"] == "a"
    assert events[2]["payload"]["type"] == "final"


@pytest.mark.asyncio
async def test_redis_two_subscribers_receive_identical_events(backend):
    channel_id = "test_redis:dual"
    await backend.create_channel(channel_id)

    events_a = []
    events_b = []

    async def consumer_a():
        async for env in backend.subscribe(channel_id):
            events_a.append(env)
            if len(events_a) >= 3:
                break

    async def consumer_b():
        async for env in backend.subscribe(channel_id):
            events_b.append(env)
            if len(events_b) >= 3:
                break

    task_a = asyncio.create_task(consumer_a())
    task_b = asyncio.create_task(consumer_b())
    await asyncio.sleep(0.2)

    await backend.publish(channel_id, {"type": "notice", "msg": "x"})
    await backend.publish(channel_id, {"type": "notice", "msg": "y"})
    await backend.publish(channel_id, {"type": "final", "msg": "end"})

    await asyncio.wait_for(task_a, timeout=5)
    await asyncio.wait_for(task_b, timeout=5)

    assert len(events_a) == 3
    assert len(events_b) == 3
    for i in range(3):
        assert events_a[i]["sequence"] == events_b[i]["sequence"]


@pytest.mark.asyncio
async def test_redis_terminal_event_closes_stream(backend):
    channel_id = "test_redis:terminal"
    await backend.create_channel(channel_id)

    events = []

    async def consumer():
        async for env in backend.subscribe(channel_id):
            events.append(env)

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.1)

    await backend.publish(channel_id, {"type": "notice", "msg": "hi"})
    await backend.publish(channel_id, {"type": "error", "msg": "fail"})

    await asyncio.wait_for(task, timeout=5)
    assert len(events) == 2
    assert events[1]["payload"]["type"] == "error"


@pytest.mark.asyncio
async def test_redis_publish_before_subscription_replays(backend):
    channel_id = "test_redis:replay"
    await backend.create_channel(channel_id)

    await backend.publish(channel_id, {"type": "notice", "msg": "historical"})

    events = []

    async def consumer():
        async for env in backend.subscribe(channel_id):
            events.append(env)
            if len(events) >= 1:
                break

    task = asyncio.create_task(consumer())
    await asyncio.wait_for(task, timeout=5)

    assert len(events) == 1
    assert events[0]["payload"]["msg"] == "historical"


@pytest.mark.asyncio
async def test_redis_reconnect_from_sequence(backend):
    channel_id = "test_redis:reconnect"
    await backend.create_channel(channel_id)

    await backend.publish(channel_id, {"type": "notice", "msg": "old"})
    await backend.publish(channel_id, {"type": "notice", "msg": "new"})

    events = []

    async def consumer():
        async for env in backend.subscribe(channel_id, last_sequence=1):
            events.append(env)
            if len(events) >= 1:
                break

    task = asyncio.create_task(consumer())
    await asyncio.wait_for(task, timeout=5)

    assert len(events) == 1
    assert events[0]["payload"]["msg"] == "new"
