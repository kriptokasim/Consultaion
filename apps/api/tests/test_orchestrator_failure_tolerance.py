import atexit
import os
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlmodel import Session

os.environ.setdefault("DATABASE_URL", "")
fd, temp_path = tempfile.mkstemp(prefix="consultaion_orchestrator_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")


def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

import config as config_module

config_module.settings.reload()

import database  # noqa: E402
from agents import UsageAccumulator  # noqa: E402

database.reset_engine()
import orchestrator  # noqa: E402
from database import init_db  # noqa: E402
from models import Debate  # noqa: E402
from parliament.engine import ParliamentResult  # noqa: E402
from schemas import default_panel_config  # noqa: E402
from sse_backend import get_sse_backend, reset_sse_backend_for_tests  # noqa: E402

init_db()


@pytest.fixture
def disable_fast_debate():
    previous = os.environ.get("FAST_DEBATE")
    os.environ["FAST_DEBATE"] = "0"
    config_module.settings.reload()
    yield
    if previous is None:
        os.environ.pop("FAST_DEBATE", None)
    else:
        os.environ["FAST_DEBATE"] = previous
    config_module.settings.reload()


@pytest.mark.anyio("asyncio")
async def test_orchestrator_marks_debate_failed(monkeypatch, disable_fast_debate):
    panel = default_panel_config()
    debate_id = f"orchestrator-failed-{uuid.uuid4().hex[:6]}"
    with Session(database.engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Abort path",
            status="queued",
            panel_config=panel.model_dump(),
            engine_version=panel.engine_version,
        )
        session.add(debate)
        session.commit()
        session.refresh(debate)

    reset_sse_backend_for_tests()
    backend = get_sse_backend()
    channel_id = f"debate:{debate_id}"
    await backend.create_channel(channel_id)

    async def _fake_parliament_run(*args, **kwargs):
        return ParliamentResult(
            final_answer="",
            final_meta={"failure": {"reason": "seat_failure_threshold_exceeded"}},
            usage_tracker=UsageAccumulator(),
            status="failed",
            error_reason="seat_failure_threshold_exceeded",
        )

    monkeypatch.setattr(orchestrator, "run_parliament_debate", _fake_parliament_run)
    await orchestrator.run_debate(
        debate_id,
        prompt="Abort path",
        channel_id=channel_id,
        config_data={},
        model_id=None,
    )

    with Session(database.engine) as session:
        debate = session.get(Debate, debate_id)
        assert debate.status == "failed"
