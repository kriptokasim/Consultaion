"""Prod-critical hardening — Compare/Conversation engine correctness.

Regression coverage for:
- ownership-fenced, attempt-scoped, idempotent message writes in both engines;
- deterministic terminal status (all-models failure must not be reported as
  completed);
- progressive persistence of compare responses (as_completed, not batched).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from database import session_scope
from models import Debate, Message
from orchestration.execution_context import ExecutionLease, bind_execution_lease
from sqlmodel import select

from config import settings


def _mk_running_debate(debate_id: str, mode: str, config: dict | None = None) -> str:
    with session_scope() as session:
        existing = session.get(Debate, debate_id)
        if existing:
            session.delete(existing)
            session.commit()
        debate = Debate(
            id=debate_id,
            prompt="hardening",
            status="running",
            mode=mode,
            user_id="u1",
            config=config or {},
        )
        session.add(debate)
        session.commit()
    return debate_id


async def _acquire_lease(debate_id: str) -> ExecutionLease:
    from orchestration.execution_lease import acquire_execution_lease

    result = await acquire_execution_lease(debate_id, lease_seconds=60)
    assert result.acquired
    return result.lease


class _MockUsage:
    def __init__(self, tokens: int = 100):
        self.prompt_tokens = 20
        self.completion_tokens = tokens - 20
        self.total_tokens = tokens
        self.cost_usd = 0.001
        self.provider = "mock"
        self.model = "mock-model"

    def to_dict(self):
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
        }


@pytest.mark.anyio
async def test_compare_persists_progressively_with_response_ids(monkeypatch):
    debate_id = _mk_running_debate(
        f"cmp-{uuid.uuid4().hex[:8]}", "compare", {"compare_models": ["m-a", "m-b"]}
    )
    lease = await _acquire_lease(debate_id)

    async def mock_call(*args, **kwargs):
        return f"answer for {kwargs.get('role')}", _MockUsage()

    mock_backend = AsyncMock()
    publish_times: list[float] = []

    async def fast_publish(channel, event):
        publish_times.append(len(publish_times))

    mock_backend.publish.side_effect = fast_publish

    with patch("compare.engine.call_llm_for_role", side_effect=mock_call), patch(
        "compare.engine.get_sse_backend", return_value=mock_backend
    ):
        token = bind_execution_lease(lease)
        try:
            result = await __import__(
                "compare.engine", fromlist=["run_compare_debate"]
            ).run_compare_debate(debate_id)
        finally:
            from orchestration.execution_context import reset_execution_lease

            reset_execution_lease(token)

    assert result.status == "completed"
    seat_events = [
        c.args[1]
        for c in mock_backend.publish.call_args_list
        if c.args[1].get("type") == "seat_message"
    ]
    assert len(seat_events) == 2
    assert all(e.get("response_id") for e in seat_events)

    with session_scope() as session:
        messages = session.exec(
            select(Message).where(Message.debate_id == debate_id)
        ).all()
        assert len(messages) == 2
        response_ids = {m.response_id for m in messages}
        assert all(r and r.startswith(f"compare:{debate_id}:a{lease.run_attempt}:") for r in response_ids)


@pytest.mark.anyio
async def test_compare_all_models_failed_is_failed_run():
    debate_id = _mk_running_debate(
        f"cmp-{uuid.uuid4().hex[:8]}", "compare", {"compare_models": ["m-a"]}
    )
    lease = await _acquire_lease(debate_id)

    async def failing_call(*args, **kwargs):
        raise RuntimeError("provider down")

    mock_backend = AsyncMock()
    with patch("compare.engine.call_llm_for_role", side_effect=failing_call), patch(
        "compare.engine.get_sse_backend", return_value=mock_backend
    ):
        token = bind_execution_lease(lease)
        try:
            result = await __import__(
                "compare.engine", fromlist=["run_compare_debate"]
            ).run_compare_debate(debate_id)
        finally:
            from orchestration.execution_context import reset_execution_lease

            reset_execution_lease(token)

    assert result.status == "failed"
    assert result.error_reason == "all_compare_models_failed"


@pytest.mark.anyio
async def test_compare_partial_failure_reports_warnings():
    debate_id = _mk_running_debate(
        f"cmp-{uuid.uuid4().hex[:8]}", "compare", {"compare_models": ["m-a", "m-b"]}
    )
    lease = await _acquire_lease(debate_id)

    async def mixed_call(*args, **kwargs):
        role = kwargs.get("role", "")
        if role == "m-b":
            raise RuntimeError("boom")
        return "ok answer", _MockUsage()

    mock_backend = AsyncMock()
    with patch("compare.engine.call_llm_for_role", side_effect=mixed_call), patch(
        "compare.engine.get_sse_backend", return_value=mock_backend
    ):
        token = bind_execution_lease(lease)
        try:
            result = await __import__(
                "compare.engine", fromlist=["run_compare_debate"]
            ).run_compare_debate(debate_id)
        finally:
            from orchestration.execution_context import reset_execution_lease

            reset_execution_lease(token)

    assert result.status == "completed_with_warnings"
    assert result.final_meta["failed_count"] == 1
    assert result.final_meta["successful_count"] == 1


@pytest.mark.anyio
async def test_conversation_empty_transcript_fails_run():
    from conversation.engine import run_conversation_debate

    debate_id = _mk_running_debate(f"cnv-{uuid.uuid4().hex[:8]}", "conversation")
    lease = await _acquire_lease(debate_id)

    async def failing_call(*args, **kwargs):
        raise RuntimeError("provider down")

    mock_backend = AsyncMock()
    with patch("conversation.engine.call_llm_for_role", side_effect=failing_call), patch(
        "conversation.engine.get_sse_backend", return_value=mock_backend
    ), patch.object(settings, "CONVERSATION_MAX_ROUNDS", 1):
        token = bind_execution_lease(lease)
        try:
            result = await run_conversation_debate(debate_id, model_id=None)
        finally:
            from orchestration.execution_context import reset_execution_lease

            reset_execution_lease(token)

    assert result.status == "failed"
    assert result.error_reason == "all_conversation_seats_failed"


@pytest.mark.anyio
async def test_conversation_messages_are_attempt_scoped_and_deduped():
    from conversation.engine import run_conversation_debate
    from schemas import default_panel_config

    debate_id = _mk_running_debate(f"cnv-{uuid.uuid4().hex[:8]}", "conversation")
    lease = await _acquire_lease(debate_id)

    async def ok_call(*args, **kwargs):
        return "contribution", _MockUsage()

    mock_backend = AsyncMock()
    with patch("conversation.engine.call_llm_for_role", side_effect=ok_call), patch(
        "conversation.engine.get_sse_backend", return_value=mock_backend
    ), patch.object(settings, "CONVERSATION_MAX_ROUNDS", 1):
        panel = default_panel_config()
        with patch("conversation.engine.PanelConfig") as pc:
            pc.model_validate.return_value = panel
            token = bind_execution_lease(lease)
            try:
                result = await run_conversation_debate(debate_id, model_id=None)
            finally:
                from orchestration.execution_context import reset_execution_lease

                reset_execution_lease(token)

    assert result.status == "completed"

    with session_scope() as session:
        messages = session.exec(
            select(Message).where(Message.debate_id == debate_id)
        ).all()
        ids = [m.response_id for m in messages]
        assert len(ids) == len(set(ids)), "duplicate message rows written"
        assert all(i.startswith(f"conversation:{debate_id}:a{lease.run_attempt}:") for i in ids if i)


def _supersede_owner(debate_id: str, lease) -> None:
    """Simulate a lease takeover: a different owner now holds a newer epoch."""

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        debate.runner_id = "other-host:999:takeover"
        debate.lease_epoch = lease.lease_epoch + 1
        debate.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        session.add(debate)
        session.commit()


@pytest.mark.anyio
async def test_compare_superseded_between_provider_and_persist_stops_completely():
    """Negative test: ownership lost after provider success but before
    persistence must raise ExecutionSupersededError, write nothing, emit no
    seat events, and cancel remaining provider work."""
    from compare.engine import run_compare_debate
    from orchestration.execution_lease import ExecutionSupersededError

    debate_id = _mk_running_debate(
        f"cmp-super-{uuid.uuid4().hex[:8]}", "compare", {"compare_models": ["m-a", "m-b"]}
    )
    lease = await _acquire_lease(debate_id)

    b_started = asyncio.Event()
    bCancelled = {"value": False}

    async def mock_call(*args, **kwargs):
        role = kwargs.get("role", "")
        if role == "m-a":
            # Provider work completes, THEN a takeover happens before persist.
            _supersede_owner(debate_id, lease)
            return "answer A", _MockUsage()
        # m-b: slow provider that should be cancelled after the takeover
        b_started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            bCancelled["value"] = True
            raise
        return "answer B", _MockUsage()

    mock_backend = AsyncMock()
    with patch("compare.engine.call_llm_for_role", side_effect=mock_call), patch(
        "compare.engine.get_sse_backend", return_value=mock_backend
    ):
        token = bind_execution_lease(lease)
        try:
            with pytest.raises(ExecutionSupersededError):
                await run_compare_debate(debate_id)
        finally:
            from orchestration.execution_context import reset_execution_lease

            reset_execution_lease(token)

    published = [c.args[1] for c in mock_backend.publish.call_args_list]
    assert not any(e.get("type") == "seat_message" for e in published), (
        "stale seat event emitted after ownership loss"
    )
    with session_scope() as session:
        messages = session.exec(
            select(Message).where(Message.debate_id == debate_id)
        ).all()
        assert messages == [], "stale worker persisted a message after takeover"
    assert bCancelled["value"], "in-flight provider work was not cancelled on takeover"


@pytest.mark.anyio
async def test_conversation_supersede_is_not_a_seat_failure():
    """Negative test: ExecutionSupersededError must propagate out of the
    conversation engine — never counted as a seat failure, never followed by
    further seats, scribe, synthesis, or settlement."""
    from conversation.engine import run_conversation_debate
    from orchestration.execution_lease import ExecutionSupersededError

    debate_id = _mk_running_debate(f"cnv-super-{uuid.uuid4().hex[:8]}", "conversation")
    lease = await _acquire_lease(debate_id)

    calls = {"count": 0}

    async def mock_call(*args, **kwargs):
        calls["count"] += 1
        # First provider call succeeds; takeover lands before persistence.
        _supersede_owner(debate_id, lease)
        return "contribution", _MockUsage()

    mock_backend = AsyncMock()
    with patch("conversation.engine.call_llm_for_role", side_effect=mock_call), patch(
        "conversation.engine.get_sse_backend", return_value=mock_backend
    ), patch.object(settings, "CONVERSATION_MAX_ROUNDS", 2):
        token = bind_execution_lease(lease)
        try:
            with pytest.raises(ExecutionSupersededError):
                await run_conversation_debate(debate_id, model_id=None)
        finally:
            from orchestration.execution_context import reset_execution_lease

            reset_execution_lease(token)

    # Exactly one provider call: the superseded worker must not start another
    # seat, scribe, or synthesis call.
    assert calls["count"] == 1
    with session_scope() as session:
        messages = session.exec(
            select(Message).where(Message.debate_id == debate_id)
        ).all()
        assert messages == [], "stale worker persisted a message after takeover"
    published = [c.args[1] for c in mock_backend.publish.call_args_list]
    assert not any(e.get("type") == "seat_message" for e in published)
