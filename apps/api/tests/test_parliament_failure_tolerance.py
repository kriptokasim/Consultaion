import uuid

import agents
import pytest
from agents import UsageCall
from models import Debate
from parliament.engine import ParliamentResult, run_parliament_debate


async def _bind_live_lease(debate_id: str):
    """Bind a real execution lease so fenced engine writes pass."""
    from orchestration.execution_context import bind_execution_lease, reset_execution_lease
    from orchestration.execution_lease import acquire_execution_lease

    acquired = await acquire_execution_lease(debate_id, lease_seconds=60)
    assert acquired.acquired
    return bind_execution_lease(acquired.lease), reset_execution_lease


from schemas import PanelSeat, default_panel_config
from sqlmodel import Session
from sse_backend import get_sse_backend, reset_sse_backend_for_tests

from config import settings


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
async def test_parliament_tolerance_allows_minor_failures(db_session: Session, monkeypatch):
    panel = default_panel_config()
    panel.max_seat_fail_ratio = 0.8
    debate_id = f"tolerance-ok-{uuid.uuid4().hex[:6]}"
    debate = Debate(
        id=debate_id,
        prompt="Resilient debate",
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

    flaky = _FlakyLLM(fail_on_calls={3})  # one failure out of three seats
    monkeypatch.setattr(agents, "call_llm_for_role", flaky)
    monkeypatch.setattr("parliament.engine.call_llm_for_role", flaky)
    token, _reset = await _bind_live_lease(debate.id)
    try:
        result: ParliamentResult = await run_parliament_debate(debate.id, model_id=None)
    finally:
        _reset(token)
    assert result.status == "completed"
    assert result.error_reason is None


@pytest.mark.anyio("asyncio")
async def test_parliament_tolerance_aborts_when_threshold_exceeded(db_session: Session, monkeypatch):
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
    debate = Debate(
        id=debate_id,
        prompt="Should abort when many seats fail",
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

    flaky = _FlakyLLM(fail_on_calls={1, 2, 3})
    monkeypatch.setattr(settings, "DEBATE_STRICT_FAIL_RATIO", True)
    monkeypatch.setattr(agents, "call_llm_for_role", flaky)
    monkeypatch.setattr("parliament.engine.call_llm_for_role", flaky)
    token, _reset = await _bind_live_lease(debate.id)
    try:
        result: ParliamentResult = await run_parliament_debate(debate.id, model_id=None)
    finally:
        _reset(token)
    assert result.status == "failed"
    assert result.error_reason == "seat_failure_threshold_exceeded"
    assert result.final_meta.get("failure", {}).get("failure_count") == 3


@pytest.mark.anyio("asyncio")
async def test_superseded_score_write_aborts_not_falls_back(db_session: Session, monkeypatch):
    """Ownership loss during the fenced Score write must propagate as
    ExecutionSupersededError — never be swallowed into a 'judging failed'
    seat-order fallback that would let a stale worker keep producing ranking."""
    from unittest.mock import patch

    from orchestration.execution_lease import ExecutionSupersededError

    panel = default_panel_config()
    panel.max_seat_fail_ratio = 0.9
    debate_id = f"supersede-judge-{uuid.uuid4().hex[:6]}"
    debate = Debate(
        id=debate_id,
        prompt="Judging ownership loss",
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

    # Seats succeed; only the judging-phase fenced Score write is superseded.
    monkeypatch.setattr(agents, "call_llm_for_role", _FlakyLLM(set()))
    monkeypatch.setattr("parliament.engine.call_llm_for_role", _FlakyLLM(set()))
    token, _reset = await _bind_live_lease(debate.id)
    try:
        with patch(
            "parliament.engine._assert_parliament_write",
            side_effect=ExecutionSupersededError("lease lost"),
        ):
            with pytest.raises(ExecutionSupersededError):
                await run_parliament_debate(debate.id, model_id=None)
    finally:
        _reset(token)
