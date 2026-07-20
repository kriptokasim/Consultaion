"""PS155.2 — Delta coalescing unit tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sse_backend import DeltaCoalescer, RedisChannelBackend, _delta_key, _is_delta


def _make_delta(response_id: str, text: str, accumulated_chars: int = 0, seq: int = 1) -> dict:
    return {
        "type": "model_response_delta",
        "payload": {
            "type": "model_response_delta",
            "response_id": response_id,
            "text": text,
            "accumulated_chars": accumulated_chars,
            "delta_sequence": seq,
        },
    }


def _make_non_delta(event_type: str = "model_response_completed") -> dict:
    return {
        "type": event_type,
        "payload": {"type": event_type, "response_id": "r1"},
    }


class TestDeltaCoalescer:
    def test_single_delta_passes_through_after_flush(self):
        """A single delta should be returned on flush interval."""
        coalescer = DeltaCoalescer(flush_interval_ms=0)  # instant flush
        result = coalescer.ingest(_make_delta("r1", "hello"))
        assert len(result) == 1
        assert result[0]["payload"]["text"] == "hello"

    def test_rapid_deltas_coalesced_within_window(self):
        """Multiple deltas within the flush window should be buffered."""
        coalescer = DeltaCoalescer(flush_interval_ms=5000)  # 5s window
        r1 = coalescer.ingest(_make_delta("r1", "hel", seq=1))
        assert r1 == []  # buffered

        r2 = coalescer.ingest(_make_delta("r1", "lo ", seq=2))
        assert r2 == []  # still buffered

        # Manual flush
        flushed = coalescer.flush_all()
        assert len(flushed) == 1
        assert flushed[0]["payload"]["text"] == "hello "

    def test_non_delta_forces_flush(self):
        """A non-delta event should flush all pending deltas first."""
        coalescer = DeltaCoalescer(flush_interval_ms=5000)

        coalescer.ingest(_make_delta("r1", "one"))
        coalescer.ingest(_make_delta("r1", "two"))

        result = coalescer.ingest(_make_non_delta())
        # Should get: coalesced delta + the non-delta
        assert len(result) == 2
        assert result[0]["payload"]["text"] == "onetwo"
        assert result[1]["type"] == "model_response_completed"

    def test_different_response_ids_coalesced_independently(self):
        """Deltas for different response_ids should be separate coalesced events."""
        coalescer = DeltaCoalescer(flush_interval_ms=5000)

        coalescer.ingest(_make_delta("r1", "aaa", seq=1))
        coalescer.ingest(_make_delta("r2", "bbb", seq=1))
        coalescer.ingest(_make_delta("r1", "ccc", seq=2))

        flushed = coalescer.flush_all()
        assert len(flushed) == 2
        texts = {f["payload"]["response_id"]: f["payload"]["text"] for f in flushed}
        assert texts["r1"] == "aaaccc"
        assert texts["r2"] == "bbb"

    def test_flush_with_no_pending_returns_empty(self):
        """Flushing with nothing pending should return empty list."""
        coalescer = DeltaCoalescer(flush_interval_ms=100)
        assert coalescer.flush_all() == []

    def test_single_delta_not_merged(self):
        """A single delta in a flush batch should not be merged (optimization)."""
        coalescer = DeltaCoalescer(flush_interval_ms=5000)
        coalescer.ingest(_make_delta("r1", "only"))
        flushed = coalescer.flush_all()
        assert len(flushed) == 1
        # Should be the original event, not a copy
        assert flushed[0]["payload"]["text"] == "only"

    def test_coalesced_event_uses_last_delta_metadata(self):
        """Merged event should use the latest delta's sequence/accumulated_chars."""
        coalescer = DeltaCoalescer(flush_interval_ms=5000)
        coalescer.ingest(_make_delta("r1", "a", accumulated_chars=1, seq=1))
        coalescer.ingest(_make_delta("r1", "b", accumulated_chars=2, seq=2))
        coalescer.ingest(_make_delta("r1", "c", accumulated_chars=3, seq=3))

        flushed = coalescer.flush_all()
        assert len(flushed) == 1
        payload = flushed[0]["payload"]
        assert payload["text"] == "abc"
        assert payload["accumulated_chars"] == 3
        assert payload["delta_sequence"] == 3

    def test_unwrapped_deltas_preserve_all_text(self):
        """The backend's public, unwrapped event shape must coalesce losslessly."""
        coalescer = DeltaCoalescer(flush_interval_ms=5000)
        for index in range(3):
            coalescer.ingest(
                {
                    "type": "model_response_delta",
                    "response_id": "r1",
                    "text": f"chunk{index}",
                    "delta_sequence": index + 1,
                }
            )

        flushed = coalescer.flush_all()
        assert len(flushed) == 1
        assert flushed[0]["text"] == "chunk0chunk1chunk2"
        assert flushed[0]["delta_sequence"] == 3


class TestHelpers:
    def test_is_delta_recognizes_model_response_delta(self):
        assert _is_delta(_make_delta("r1", "x")) is True

    def test_is_delta_rejects_non_delta(self):
        assert _is_delta(_make_non_delta()) is False

    def test_delta_key_extracts_response_id(self):
        assert _delta_key(_make_delta("r1", "x")) == "r1"

    def test_delta_key_returns_none_for_non_delta(self):
        assert _delta_key({"payload": {}}) is None


@pytest.mark.asyncio
async def test_redis_backend_coalesces_deltas_before_lifecycle_event():
    """Production Redis transport must match memory coalescing semantics."""
    backend = RedisChannelBackend.__new__(RedisChannelBackend)
    backend._redis = AsyncMock()
    backend._redis.incr.side_effect = [1, 2]
    history_pipeline = MagicMock()
    history_pipeline.rpush.return_value = history_pipeline
    history_pipeline.expire.return_value = history_pipeline
    history_pipeline.ltrim.return_value = history_pipeline
    history_pipeline.execute = AsyncMock(return_value=[1, True, True])
    backend._redis.pipeline = MagicMock(return_value=history_pipeline)
    backend._ttl_seconds = 60
    backend._max_queue_size = 100
    backend._coalescers = {}
    backend._coalescer_flush_tasks = {}

    await backend.publish("debate:d1", _make_delta("r1", "hello", 5, 1))
    await backend.publish("debate:d1", _make_delta("r1", " world", 11, 2))
    await backend.publish("debate:d1", _make_non_delta())

    published = [json.loads(call.args[1]) for call in backend._redis.publish.await_args_list]
    assert len(published) == 2
    assert published[0]["payload"]["payload"]["text"] == "hello world"
    assert published[0]["payload"]["payload"]["delta_sequence"] == 2
    assert published[1]["payload"]["type"] == "model_response_completed"


@pytest.mark.asyncio
async def test_redis_backend_pipelines_history_maintenance():
    """History append, expiry, and trim should use one Redis round trip."""
    backend = RedisChannelBackend.__new__(RedisChannelBackend)
    backend._redis = AsyncMock()
    backend._redis.incr.return_value = 1
    history_pipeline = MagicMock()
    history_pipeline.rpush.return_value = history_pipeline
    history_pipeline.expire.return_value = history_pipeline
    history_pipeline.ltrim.return_value = history_pipeline
    history_pipeline.execute = AsyncMock(return_value=[1, True, True])
    backend._redis.pipeline = MagicMock(return_value=history_pipeline)
    backend._ttl_seconds = 60
    backend._max_queue_size = 100
    backend._coalescers = {}
    backend._coalescer_flush_tasks = {}

    await backend.publish("debate:d1", _make_non_delta("notice"))

    backend._redis.pipeline.assert_called_once_with(transaction=False)
    history_pipeline.rpush.assert_called_once()
    history_pipeline.expire.assert_called_once_with("sse:history:debate:d1", 60)
    history_pipeline.ltrim.assert_called_once_with("sse:history:debate:d1", -100, -1)
    history_pipeline.execute.assert_awaited_once()
