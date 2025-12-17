"""Patchset 75: Memory backend limits and safeguards tests."""
import asyncio
import time

import pytest
from sse_backend import MemoryChannelBackend


@pytest.mark.asyncio
class TestSSEMemoryLimits:
    """Tests for memory backend bounded queues and idle timeout."""
    
    async def test_queue_size_bounded_drops_oldest(self):
        """Queue should drop oldest event when full."""
        backend = MemoryChannelBackend(ttl_seconds=900, max_queue_size=3)
        channel = "test:bounded"
        await backend.create_channel(channel)
        
        # Publish 5 events to a queue with max size 3
        for i in range(5):
            await backend.publish(channel, {"type": "event", "index": i})
        
        # Should only have the last 3 events (indices 2, 3, 4)
        events = []
        async for event in backend.subscribe(channel):
            events.append(event)
            if len(events) >= 3:
                break
        
        indices = [e.get("index") for e in events]
        assert indices == [2, 3, 4], f"Expected [2, 3, 4], got {indices}"
    
    async def test_queue_does_not_grow_unbounded(self):
        """Queue size should never exceed max_queue_size."""
        backend = MemoryChannelBackend(ttl_seconds=900, max_queue_size=10)
        channel = "test:bounded2"
        await backend.create_channel(channel)
        
        # Publish 100 events
        for i in range(100):
            await backend.publish(channel, {"type": "event", "index": i})
        
        # Check internal queue size
        queue = backend._channels[channel]
        assert queue.qsize() <= 10
    
    async def test_subscribe_exits_on_final_event(self):
        """Subscription should exit on final event type."""
        backend = MemoryChannelBackend(ttl_seconds=900, max_queue_size=100)
        channel = "test:final"
        await backend.create_channel(channel)
        
        events = []
        
        async def publish_events():
            await asyncio.sleep(0.01)
            await backend.publish(channel, {"type": "round_started", "round": 1})
            await backend.publish(channel, {"type": "round_ended", "round": 1})
            await backend.publish(channel, {"type": "final", "result": "done"})
            # This should not be received
            await backend.publish(channel, {"type": "extra", "should": "ignore"})
        
        publisher = asyncio.create_task(publish_events())
        async for event in backend.subscribe(channel):
            events.append(event)
        await publisher
        
        assert len(events) == 3
        assert events[-1]["type"] == "final"
    
    async def test_subscribe_exits_on_error_event(self):
        """Subscription should exit on error event type."""
        backend = MemoryChannelBackend(ttl_seconds=900, max_queue_size=100)
        channel = "test:error"
        await backend.create_channel(channel)
        
        events = []
        
        async def publish_events():
            await asyncio.sleep(0.01)
            await backend.publish(channel, {"type": "round_started", "round": 1})
            await backend.publish(channel, {"type": "error", "message": "Something failed"})
        
        publisher = asyncio.create_task(publish_events())
        async for event in backend.subscribe(channel):
            events.append(event)
        await publisher
        
        assert len(events) == 2
        assert events[-1]["type"] == "error"
    
    async def test_subscribe_exits_on_idle_timeout(self):
        """Subscription should exit after idle timeout."""
        # Very short idle timeout for testing
        backend = MemoryChannelBackend(
            ttl_seconds=900, 
            max_queue_size=100, 
            idle_timeout_seconds=1  # 1 second timeout
        )
        channel = "test:idle"
        await backend.create_channel(channel)
        
        start = time.time()
        events = []
        async for event in backend.subscribe(channel):
            events.append(event)
        elapsed = time.time() - start
        
        # Should exit due to idle timeout, not hang forever
        assert elapsed >= 1.0
        assert elapsed < 5.0  # Should exit reasonably quickly
        assert len(events) == 0  # No events published
    
    async def test_idle_timeout_resets_on_event(self):
        """Idle timer should reset when event is received."""
        backend = MemoryChannelBackend(
            ttl_seconds=900, 
            max_queue_size=100, 
            idle_timeout_seconds=2  # 2 second timeout
        )
        channel = "test:idle_reset"
        await backend.create_channel(channel)
        
        events = []
        
        async def publish_delayed():
            # Publish at 0.5s - before idle timeout
            await asyncio.sleep(0.5)
            await backend.publish(channel, {"type": "event", "index": 1})
            # Publish at 1.0s - before idle timeout (reset at 0.5s)
            await asyncio.sleep(0.5)
            await backend.publish(channel, {"type": "final"})
        
        publisher = asyncio.create_task(publish_delayed())
        async for event in backend.subscribe(channel):
            events.append(event)
        await publisher
        
        # Should have received both events before timeout
        assert len(events) == 2
