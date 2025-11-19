import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")

import routes.common as common_routes  # noqa: E402
from routes.common import CHANNELS, CHANNEL_META, cleanup_channel, sweep_stale_channels  # noqa: E402

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(autouse=True)
def clear_channels():
    CHANNELS.clear()
    CHANNEL_META.clear()
    yield
    CHANNELS.clear()
    CHANNEL_META.clear()


@pytest.mark.anyio("asyncio")
async def test_channel_creation_and_cleanup():
    debate_id = "sse-test"
    queue = asyncio.Queue()
    CHANNELS[debate_id] = queue
    CHANNEL_META[debate_id] = asyncio.get_running_loop().time()
    assert debate_id in CHANNELS

    cleanup_channel(debate_id)
    assert debate_id not in CHANNELS
    assert debate_id not in CHANNEL_META


@pytest.mark.anyio("asyncio")
async def test_stream_queue_drains_events():
    debate_id = "sse-stream"
    queue = asyncio.Queue()
    CHANNELS[debate_id] = queue
    CHANNEL_META[debate_id] = asyncio.get_running_loop().time()

    payloads = [
        {"type": "round_started", "round": 1},
        {"type": "message", "round": 1},
        {"type": "final", "content": "done"},
    ]
    for payload in payloads:
        await queue.put(payload)

    received = []
    while not queue.empty():
        received.append(await queue.get())
    assert [evt["type"] for evt in received] == ["round_started", "message", "final"]


@pytest.mark.anyio("asyncio")
async def test_sweep_stale_channels_removes_old_entries():
    ttl_original = common_routes.CHANNEL_TTL_SECS
    common_routes.CHANNEL_TTL_SECS = 5
    loop = asyncio.get_running_loop()
    now = loop.time()
    CHANNEL_META["old"] = now - 10
    CHANNEL_META["fresh"] = now
    CHANNELS["old"] = asyncio.Queue()
    CHANNELS["fresh"] = asyncio.Queue()

    stale = sweep_stale_channels(now=now)
    assert "old" in stale
    assert "old" not in CHANNELS
    assert "fresh" in CHANNELS
    common_routes.CHANNEL_TTL_SECS = ttl_original


@pytest.mark.anyio("asyncio")
async def test_channel_metadata_updates():
    debate_id = "meta-test"
    queue = asyncio.Queue()
    CHANNELS[debate_id] = queue
    loop = asyncio.get_running_loop()
    first = loop.time()
    CHANNEL_META[debate_id] = first

    later = loop.time() + 5
    CHANNEL_META[debate_id] = later
    assert CHANNEL_META[debate_id] == later
