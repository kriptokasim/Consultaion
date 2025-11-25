import asyncio
import os
import sys
from pathlib import Path

import pytest
from sqlmodel import Session

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./sse_test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SSE_BACKEND", "memory")
os.environ.setdefault("USE_MOCK", "1")

from database import engine, init_db  # noqa: E402
from models import Debate  # noqa: E402
from routes.debates import stream_events  # noqa: E402
from schemas import default_debate_config  # noqa: E402
from sse_backend import (  # noqa: E402
    MemoryChannelBackend,
    get_sse_backend,
    reset_sse_backend_for_tests,
)

init_db()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_memory_backend_publish_and_subscribe():
    backend = MemoryChannelBackend(ttl_seconds=30)
    channel = "debate:test"
    await backend.create_channel(channel)
    events: list[dict] = []

    async def consume():
        async for event in backend.subscribe(channel):
            events.append(event)
            if event.get("type") == "final":
                break

    consumer = asyncio.create_task(consume())
    await backend.publish(channel, {"type": "round_started"})
    await backend.publish(channel, {"type": "final"})
    await consumer

    assert [evt["type"] for evt in events] == ["round_started", "final"]


@pytest.mark.anyio("asyncio")
async def test_memory_backend_cleanup_removes_stale_channels():
    backend = MemoryChannelBackend(ttl_seconds=0)
    await backend.create_channel("debate:old")
    await backend.cleanup()
    assert "debate:old" not in backend._channels  # type: ignore[attr-defined]


@pytest.mark.anyio("asyncio")
async def test_stream_events_uses_backend():
    reset_sse_backend_for_tests()
    backend = get_sse_backend()
    debate_id = "stream-test"
    channel_id = f"debate:{debate_id}"
    await backend.create_channel(channel_id)

    with Session(engine) as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            session.add(
                Debate(
                    id=debate_id,
                    prompt="Stream prompt",
                    status="queued",
                    config=default_debate_config().model_dump(),
                )
            )
            session.commit()

        response = await stream_events(debate_id, session=session, current_user=None)

        async def publish_final():
            await asyncio.sleep(0.01)
            await backend.publish(channel_id, {"type": "final", "content": "done"})

        publisher = asyncio.create_task(publish_final())
        received = bytearray()
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            data = chunk if isinstance(chunk, (bytes, bytearray)) else chunk.encode()
            received.extend(data)
            if b"final" in data:
                break
        await publisher

    assert b"final" in received
