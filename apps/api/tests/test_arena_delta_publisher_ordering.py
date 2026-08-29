from __future__ import annotations

import asyncio

import pytest

from arena.delta_publisher import ArenaDeltaPublisher, MAX_INTERACTIVE_FLUSH_MS
from model_gateway.types import ModelDelta


@pytest.mark.anyio
async def test_delta_publishes_are_serialized_in_sequence_order():
    received: list[tuple[int, str]] = []

    async def publish(event: dict) -> None:
        # Make the first transport call deliberately slower. A publisher that
        # fires independent background tasks can let seq=2 overtake seq=1.
        if event["delta_sequence"] == 1:
            await asyncio.sleep(0.02)
        received.append((event["delta_sequence"], event["text"]))

    publisher = ArenaDeltaPublisher(
        publish,
        response_id="resp-1",
        model_id="model-1",
        flush_interval_ms=10,
        max_chars=1,
    )
    await publisher.start()
    await publisher.push(ModelDelta(text="A", sequence=1, accumulated_chars=1))
    await publisher.push(ModelDelta(text="B", sequence=2, accumulated_chars=2))
    await publisher.close()

    assert received == [(1, "A"), (2, "B")]


def test_historical_slow_flush_setting_is_capped_for_interactive_streaming():
    publisher = ArenaDeltaPublisher(
        lambda _event: None,
        response_id="resp-1",
        model_id="model-1",
        flush_interval_ms=150,
    )

    assert publisher._flush_interval_ms == MAX_INTERACTIVE_FLUSH_MS
    assert publisher._flush_interval_ms <= 50
