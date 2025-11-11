import asyncio
import os
from pathlib import Path

import pytest
from sqlmodel import Session

os.environ['DATABASE_URL'] = 'sqlite:///./test_ci.db'
os.environ.setdefault('USE_MOCK', '1')

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import engine, init_db  # noqa: E402
from main import healthz  # noqa: E402
from models import Debate  # noqa: E402
from orchestrator import run_debate  # noqa: E402
from schemas import default_debate_config  # noqa: E402

init_db()


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_health_endpoint_direct():
    result = healthz()
    assert result['ok'] is True


@pytest.mark.anyio
async def test_run_debate_emits_final_events():
    debate_id = 'pytest-debate'
    with Session(engine) as session:
        existing = session.get(Debate, debate_id)
        if existing:
            session.delete(existing)
            session.commit()
        session.add(
            Debate(
                id=debate_id,
                prompt='Pytest prompt',
                status='queued',
                config=default_debate_config().model_dump(),
            )
        )
        session.commit()

    q: asyncio.Queue = asyncio.Queue()
    await run_debate(debate_id, 'Pytest prompt', q, default_debate_config().model_dump())

    events = []
    while not q.empty():
        events.append(await q.get())

    final_events = [event for event in events if event.get('type') == 'final']
    assert final_events, f"No final event emitted: {events}"
    meta = final_events[-1]['meta']
    assert 'ranking' in meta
    assert 'usage' in meta
