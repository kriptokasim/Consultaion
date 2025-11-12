import asyncio
import os
import sys
import tempfile
from pathlib import Path
import atexit

import pytest
from sqlmodel import Session

fd, temp_path = tempfile.mkstemp(prefix="consultaion_test_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)

def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass

atexit.register(_cleanup)

os.environ['DATABASE_URL'] = f'sqlite:///{test_db_path}'
os.environ.setdefault('USE_MOCK', '1')

sys.path.append(str(Path(__file__).resolve().parents[1]))

from database import engine, init_db  # noqa: E402
from main import export_scores_csv, healthz  # noqa: E402
from models import Debate, Score  # noqa: E402
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


def test_export_scores_csv_endpoint():
    debate_id = 'csv-export'
    with Session(engine) as session:
        existing = session.get(Debate, debate_id)
        if existing:
            session.delete(existing)
            session.commit()
        session.add(
            Debate(
                id=debate_id,
                prompt='CSV prompt',
                status='completed',
                config=default_debate_config().model_dump(),
            )
        )
        session.commit()
        session.add(
            Score(
                debate_id=debate_id,
                persona='Analyst',
                judge='JudgeOne',
                score=8.5,
                rationale='Strong analysis',
            )
        )
        session.add(
            Score(
                debate_id=debate_id,
                persona='Builder',
                judge='JudgeOne',
                score=7.0,
                rationale='Actionable plan',
            )
        )
        session.commit()

    with Session(engine) as session:
        response = asyncio.run(export_scores_csv(debate_id, session=session))
    assert response.media_type == "text/csv"
    assert "persona,judge,score,rationale,timestamp" in response.body.decode()
    assert "Analyst" in response.body.decode()
