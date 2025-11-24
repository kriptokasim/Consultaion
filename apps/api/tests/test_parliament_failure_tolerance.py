import os
import uuid
from pathlib import Path

import pytest
from sqlmodel import Session


import agents  # noqa: E402
from agents import UsageCall  # noqa: E402
from database import engine  # noqa: E402
from models import Debate  # noqa: E402
from parliament.engine import ParliamentResult, run_parliament_debate  # noqa: E402
from schemas import PanelSeat, default_panel_config  # noqa: E402
from sse_backend import get_sse_backend, reset_sse_backend_for_tests  # noqa: E402


class _FlakyLLM:
    def __init__(self, fail_on_calls):
        self.calls = 0
        self.fail_on_calls = set(fail_on_calls)

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls in self.fail_on_calls:
            raise RuntimeError("seat failed")
        return '{"content":"ok","stance":"support"}', UsageCall(provider="mock", model="mock-model", total_tokens=5)


@pytest.mark.anyio("asyncio")
async def test_parliament_tolerance_allows_minor_failures(monkeypatch):
    panel = default_panel_config()
    panel.max_seat_fail_ratio = 0.8
    debate_id = f"tolerance-ok-{uuid.uuid4().hex[:6]}"
    with Session(engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Resilient debate",
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

    flaky = _FlakyLLM(fail_on_calls={3})  # one failure out of three seats
    monkeypatch.setattr(agents, "call_llm_for_role", flaky)
    monkeypatch.setattr("parliament.engine.call_llm_for_role", flaky)
    result: ParliamentResult = await run_parliament_debate(debate, model_id=None)
    assert result.status == "completed"
    assert result.error_reason is None


@pytest.mark.anyio("asyncio")
async def test_parliament_tolerance_aborts_when_threshold_exceeded(monkeypatch):
    panel = default_panel_config()
    panel.max_seat_fail_ratio = 0.2
    panel.fail_fast = True
    panel.seats.append(
        PanelSeat(
            seat_id="extra",
            display_name="Extra",
            provider_key="openai",
            model="gpt-4o-mini",
            role_profile="builder",
            temperature=0.5,
        )
    )
    debate_id = f"tolerance-fail-{uuid.uuid4().hex[:6]}"
    with Session(engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Should abort when many seats fail",
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

    flaky = _FlakyLLM(fail_on_calls={1, 2, 3})
    monkeypatch.setattr(agents, "call_llm_for_role", flaky)
    monkeypatch.setattr("parliament.engine.call_llm_for_role", flaky)
    result: ParliamentResult = await run_parliament_debate(debate, model_id=None)
    assert result.status == "failed"
    assert result.error_reason == "seat_failure_threshold_exceeded"
    assert result.final_meta.get("failure", {}).get("failure_count") == 3
