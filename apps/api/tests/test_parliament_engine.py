import pytest
from sqlmodel import Session

from agents import UsageCall
from database import engine
from models import Debate
from parliament.engine import run_parliament_debate
from parliament.prompts import build_messages_for_seat
from schemas import default_panel_config
from sse_backend import get_sse_backend, reset_sse_backend_for_tests


def test_build_messages_include_role_details():
    panel = default_panel_config()
    seat = panel.seats[0].model_dump()
    debate = Debate(id="demo", prompt="Assess renewable incentives", status="queued")
    messages = build_messages_for_seat(
        debate_id=debate.id,
        prompt=debate.prompt,
        seat=seat,
        round_info={"index": 1, "phase": "explore", "task_for_seat": "Surface arguments."},
        transcript="None yet.",
    )
    assert messages[0]["role"] == "system"
    assert "Parliament" in messages[0]["content"]
    assert seat["display_name"] in messages[1]["content"]


@pytest.mark.anyio("asyncio")
async def test_parliament_engine_runs_with_mock_llm(db_session: Session):
    panel = default_panel_config()
    debate_id = "parliament-run"
    debate = Debate(
        id=debate_id,
        prompt="Outline a lunar mining policy",
        status="queued",
        panel_config=panel.model_dump(),
        engine_version=panel.engine_version,
    )
    db_session.add(debate)
    db_session.commit()
    db_session.refresh(debate)

    reset_sse_backend_for_tests()
    backend = get_sse_backend()
    await backend.create_channel(f"debate:{debate_id}")
    result = await run_parliament_debate(debate.id, model_id=None)
    assert result.final_meta["panel"]["engine_version"] == panel.engine_version
    assert result.final_meta["seat_usage"], "seat usage should be recorded"
    assert isinstance(result.final_answer, str) and result.final_answer


@pytest.mark.anyio("asyncio")
async def test_parliament_engine_parses_structured_output(db_session: Session, monkeypatch):
    panel = default_panel_config()
    debate_id = "parliament-structured"
    debate = Debate(
        id=debate_id,
        prompt="Structured parliament prompt",
        status="queued",
        panel_config=panel.model_dump(),
        engine_version=panel.engine_version,
    )
    db_session.add(debate)
    db_session.commit()
    db_session.refresh(debate)

    async def fake_call(messages, role, temperature=0.3, model_override=None, model_id=None, debate_id=None):
        return (
            '{"content":"Structured response","stance":"support","reasoning":"coherent"}',
            UsageCall(total_tokens=10, provider="mock", model="mock-model"),
        )

    monkeypatch.setattr("parliament.engine.call_llm_for_role", fake_call)

    reset_sse_backend_for_tests()
    backend = get_sse_backend()
    await backend.create_channel(f"debate:{debate_id}")
    result = await run_parliament_debate(debate.id, model_id=None)
    assert result.final_meta["seat_usage"]
