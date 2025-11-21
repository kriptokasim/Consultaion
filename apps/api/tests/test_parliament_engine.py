import atexit
import os
import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session

os.environ.setdefault("DATABASE_URL", "")
fd, temp_path = tempfile.mkstemp(prefix="consultaion_parliament_", suffix=".db")
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

from database import engine, init_db  # noqa: E402
from models import Debate  # noqa: E402
from parliament.engine import run_parliament_debate  # noqa: E402
from parliament.prompts import build_messages_for_seat  # noqa: E402
from schemas import default_panel_config  # noqa: E402
from sse_backend import get_sse_backend, reset_sse_backend_for_tests  # noqa: E402

init_db()


def test_build_messages_include_role_details():
    panel = default_panel_config()
    seat = panel.seats[0].model_dump()
    debate = Debate(id="demo", prompt="Assess renewable incentives", status="queued")
    messages = build_messages_for_seat(
        debate=debate,
        seat=seat,
        round_info={"index": 1, "phase": "explore", "task_for_seat": "Surface arguments."},
        transcript="None yet.",
    )
    assert messages[0]["role"] == "system"
    assert "Parliament" in messages[0]["content"]
    assert seat["display_name"] in messages[1]["content"]


@pytest.mark.anyio("asyncio")
async def test_parliament_engine_runs_with_mock_llm():
    panel = default_panel_config()
    debate_id = "parliament-run"
    with Session(engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Outline a lunar mining policy",
            status="queued",
            panel_config=panel.model_dump(),
            engine_version=panel.engine_version,
        )
        session.add(debate)
        session.commit()
        session.refresh(debate)

    reset_sse_backend_for_tests()
    backend = get_sse_backend()
    await backend.create_channel(f"debate:{debate_id}")
    result = await run_parliament_debate(debate, model_id=None)
    assert result.final_meta["panel"]["engine_version"] == panel.engine_version
    assert result.final_meta["seat_usage"], "seat usage should be recorded"
    assert isinstance(result.final_answer, str) and result.final_answer
