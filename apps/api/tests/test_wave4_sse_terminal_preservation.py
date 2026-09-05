import asyncio

from sse_backend import CRITICAL_NON_TERMINAL_EVENT_TYPES, MemoryChannelBackend


def test_terminal_event_is_never_evicted_from_full_critical_queue():
    backend = MemoryChannelBackend(max_queue_size=3)
    queue = asyncio.Queue(maxsize=3)
    queue.put_nowait({"type": "model_response_completed"})
    queue.put_nowait({"type": "final"})
    queue.put_nowait({"type": "model_response_failed"})

    assert backend._drop_oldest_non_terminal_critical(queue) is True
    remaining = list(queue._queue)
    event_types = {item["type"] for item in remaining}

    assert "final" in event_types
    assert any(item["type"] in CRITICAL_NON_TERMINAL_EVENT_TYPES for item in remaining)

