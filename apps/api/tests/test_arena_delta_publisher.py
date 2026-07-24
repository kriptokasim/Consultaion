"""PS157 Track I: ArenaDeltaPublisher tests."""

from __future__ import annotations

import pytest
from arena.delta_publisher import ArenaDeltaPublisher
from model_gateway.types import ModelDelta


@pytest.fixture
def collected():
    return []


@pytest.fixture
def publisher(collected):
    def publish_fn(event: dict) -> None:
        collected.append(event)
    return ArenaDeltaPublisher(
        publish_fn=publish_fn,
        response_id="resp-test-a1-g0-model-x-abc",
        model_id="model-x",
    )


@pytest.mark.asyncio
async def test_first_delta_published_immediately(publisher, collected):
    await publisher.push(ModelDelta(text="Hello", sequence=1, accumulated_chars=5))
    assert len(collected) == 1
    assert collected[0]["text"] == "Hello"
    assert collected[0]["response_id"] == "resp-test-a1-g0-model-x-abc"


@pytest.mark.asyncio
async def test_subsequent_deltas_are_batched(publisher, collected):
    await publisher.push(ModelDelta(text="Hello", sequence=1, accumulated_chars=5))
    await publisher.push(ModelDelta(text=" world", sequence=2, accumulated_chars=11))
    await publisher.push(ModelDelta(text="!", sequence=3, accumulated_chars=12))
    # First was immediate; rest are pending
    assert len(collected) == 1
    await publisher.flush()
    assert len(collected) == 2
    assert collected[1]["text"] == " world!"
    assert collected[1]["accumulated_chars"] == 12
    assert collected[1]["delta_sequence"] == 3


@pytest.mark.asyncio
async def test_flush_empty_is_noop(publisher, collected):
    await publisher.flush()
    assert len(collected) == 0


@pytest.mark.asyncio
async def test_close_stops_future_pushes(publisher, collected):
    await publisher.push(ModelDelta(text="First", sequence=1, accumulated_chars=5))
    await publisher.close()
    await publisher.push(ModelDelta(text="Second", sequence=2, accumulated_chars=10))
    assert len(collected) == 1  # Second rejected after close


@pytest.mark.asyncio
async def test_fail_closes(publisher, collected):
    await publisher.push(ModelDelta(text="First", sequence=1, accumulated_chars=5))
    await publisher.fail()
    await publisher.push(ModelDelta(text="Second", sequence=2, accumulated_chars=10))
    assert len(collected) == 1  # Second rejected after fail/close


@pytest.mark.asyncio
async def test_flush_before_close_publishes_pending(publisher, collected):
    await publisher.push(ModelDelta(text="A", sequence=1, accumulated_chars=1))
    await publisher.push(ModelDelta(text="B", sequence=2, accumulated_chars=2))
    await publisher.close()
    # close flushes pending deltas
    assert len(collected) == 2
    assert collected[1]["text"] == "B"


@pytest.mark.asyncio
async def test_max_chars_triggers_flush(publisher, collected):
    pub = ArenaDeltaPublisher(
        publish_fn=lambda e: collected.append(e),
        response_id="r1",
        model_id="m1",
        max_chars=10,
    )
    await pub.push(ModelDelta(text="short", sequence=1, accumulated_chars=5))
    assert len(collected) == 1  # first immediate
    await pub.push(ModelDelta(text="12345678901", sequence=2, accumulated_chars=16))
    assert len(collected) == 2  # exceeded max_chars → flushed


@pytest.mark.asyncio
async def test_max_items_triggers_flush(publisher, collected):
    pub = ArenaDeltaPublisher(
        publish_fn=lambda e: collected.append(e),
        response_id="r1",
        model_id="m1",
        max_items=2,
    )
    await pub.push(ModelDelta(text="a", sequence=1, accumulated_chars=1))
    await pub.push(ModelDelta(text="b", sequence=2, accumulated_chars=2))
    await pub.push(ModelDelta(text="c", sequence=3, accumulated_chars=3))
    # 1st immediate, 2nd-3rd pending → 3rd hits max_items → flush
    assert len(collected) == 2


@pytest.mark.asyncio
async def test_merge_maintains_single_model_id(publisher, collected):
    await publisher.push(ModelDelta(text="A", sequence=1, accumulated_chars=1))
    await publisher.push(ModelDelta(text="B", sequence=2, accumulated_chars=2))
    await publisher.flush()
    assert all(e["model_id"] == "model-x" for e in collected)


@pytest.mark.asyncio
async def test_custom_synthesis_event_preserves_versioned_identity(collected):
    pub = ArenaDeltaPublisher(
        publish_fn=lambda event: collected.append(event),
        response_id="synth-debate-a2-r0",
        model_id="synthesizer",
        event_type="arena_synthesis_delta",
        extra_payload={
            "contract_version": 1,
            "run_attempt": 2,
            "revision": 0,
            "status": "provisional",
            "response_ids": ["response-a"],
        },
    )

    await pub.push(ModelDelta(text="Draft", sequence=1, accumulated_chars=5))
    await pub.close()

    assert collected == [
        {
            "type": "arena_synthesis_delta",
            "_already_coalesced": True,
            "response_id": "synth-debate-a2-r0",
            "model_id": "synthesizer",
            "text": "Draft",
            "delta_sequence": 1,
            "accumulated_chars": 5,
            "contract_version": 1,
            "run_attempt": 2,
            "revision": 0,
            "status": "provisional",
            "response_ids": ["response-a"],
        }
    ]


@pytest.mark.asyncio
async def test_publish_failure_does_not_raise(publisher, collected):
    def failing(_):
        raise RuntimeError("publish failed")
    pub = ArenaDeltaPublisher(
        publish_fn=failing,
        response_id="r1",
        model_id="m1",
    )
    await pub.push(ModelDelta(text="test", sequence=1, accumulated_chars=4))
    # No exception should propagate
