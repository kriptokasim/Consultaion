import asyncio

from sse_backend import CRITICAL_NON_TERMINAL_EVENT_TYPES, MemoryChannelBackend


def test_terminal_event_survives_critical_queue_eviction():
    backend = MemoryChannelBackend(max_queue_size=3)
    queue = asyncio.Queue(maxsize=3)
    queue.put_nowait({"type": "model_response_completed"})
    queue.put_nowait({"type": "final"})
    queue.put_nowait({"type": "model_response_failed"})
    assert backend._drop_oldest_non_terminal_critical(queue) is True
    assert "final" in {item["type"] for item in queue._queue}
    assert any(item["type"] in CRITICAL_NON_TERMINAL_EVENT_TYPES for item in queue._queue)
