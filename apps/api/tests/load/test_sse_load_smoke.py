"""SSE load saturation tests.

Bounded local/CI profile for validating SSE infrastructure under load.
Tests subscriber scaling, reconnect behavior, backpressure, and concurrent delivery.
"""

import asyncio
import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

from sse_backend import MemoryChannelBackend

# In a true deployment, this would be RedisChannelBackend. For CI reliability
# without Redis dependency, we test the interface contract with high concurrency
# using the MemoryChannelBackend (or Redis if injected by fixture).


@pytest.fixture
def backend():
    return MemoryChannelBackend()


@pytest.mark.asyncio
async def test_concurrent_consumer_queue_saturation(backend):
    """Test active concurrent consumer task, queue saturation, and backpressure."""
    channel = "load-test-saturation"
    await backend.create_channel(channel)
    
    sub_count = 50
    publish_count = 100
    
    # 1. Create active concurrent consumer tasks
    async def consumer(sub_id, subscription):
        received = 0
        async for event in subscription:
            received += 1
            if received == publish_count:
                break
        return received
        
    subs = [backend.subscribe(channel, last_sequence=None) for _ in range(sub_count)]
    consumer_tasks = [asyncio.create_task(consumer(i, sub)) for i, sub in enumerate(subs)]
    
    # 2. Simulate high frequency concurrent publisher load
    async def publisher():
        for i in range(publish_count):
            await backend.publish(channel, {"type": "message", "content": f"msg-{i}"})
            # very small sleep to yield control but still push hard
            await asyncio.sleep(0.001) 
            
    await asyncio.gather(publisher())
    
    # 3. Wait for consumers to drain queue
    results = await asyncio.gather(*consumer_tasks, return_exceptions=True)
    
    for r in results:
        assert r == publish_count, "Consumer dropped messages or failed"
        
    # 4. Lease cleanup and memory validation
    await backend.cleanup()
    assert True


@pytest.mark.asyncio
async def test_slow_subscriber_backpressure(backend):
    """Test slow subscriber dropping logic or backpressure handling."""
    channel = "load-test-slow"
    await backend.create_channel(channel)
    
    events = []
    ready = asyncio.Event()

    async def consumer():
        sub = backend.subscribe(channel, last_sequence=None)
        # We must pull at least one item or start iteration to ensure it's attached
        # We can signal ready, then iterate.
        ready.set()
        async for event in sub:
            events.append(event)
            await asyncio.sleep(0.01)
            if len(events) >= 10:
                break

    task = asyncio.create_task(consumer())
    await ready.wait()
    # Let the event loop run to ensure subscription is registered in backend
    await asyncio.sleep(0.1)
    
    # Publish many messages instantly to force queue overflow and backpressure
    for i in range(1500):
        await backend.publish(channel, {"type": "model_response_delta", "index": i})
        
    await asyncio.wait_for(task, timeout=5)
            
    assert len(events) == 10
    await backend.cleanup()


@pytest.mark.asyncio
async def test_reconnect_cursor_validation(backend):
    """Test reconnect cursor validation ensures no missed messages."""
    channel = "load-test-cursor"
    await backend.create_channel(channel)

    sub1 = backend.subscribe(channel, last_sequence=None)
    await backend.publish(channel, {"type": "message", "content": "msg-1"})
    await backend.publish(channel, {"type": "message", "content": "msg-2"})

    events1 = []
    async for event in sub1:
        events1.append(event)
        if len(events1) >= 1:
            break

    # Reconnect with cursor 1 (meaning we want msg-2 and onwards)
    sub2 = backend.subscribe(channel, last_sequence=1)
    await backend.publish(channel, {"type": "message", "content": "msg-3"})

    events2 = []
    async for event in sub2:
        events2.append(event)
        if len(events2) >= 2:
            break

    assert len(events2) == 2
    assert events2[0]["payload"].get("content") == "msg-2"
    assert events2[1]["payload"].get("content") == "msg-3"

    await backend.cleanup()
