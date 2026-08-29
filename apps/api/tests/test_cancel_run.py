from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from database import session_scope
from models import Debate, DebateAttempt, DebateStageCheckpoint, User
from routes.debates import cancel as cancel_module


class _FakeBackend:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def publish(self, channel: str, event: dict) -> None:
        self.events.append((channel, event))


def _make_user_and_run(*, status: str = "running") -> tuple[str, str]:
    suffix = uuid.uuid4().hex
    user_id = f"cancel-user-{suffix}"
    debate_id = f"cancel-run-{suffix}"
    with session_scope() as session:
        user = User(
            id=user_id,
            email=f"{suffix}@cancel.test",
            password_hash="test",
        )
        debate = Debate(
            id=debate_id,
            prompt="Stop me",
            status=status,
            user_id=user_id,
            run_attempt=1,
            runner_id="worker-old",
            execution_owner_id="worker-old",
            lease_epoch=4,
        )
        attempt = DebateAttempt(
            debate_id=debate_id,
            attempt_number=1,
            status="running",
        )
        checkpoint = DebateStageCheckpoint(
            debate_id=debate_id,
            stage_key="arena_perspectives",
            status="running",
            input_hash="abc",
            owner_id="worker-old",
            lease_epoch=4,
        )
        session.add(user)
        session.add(debate)
        session.add(attempt)
        session.add(checkpoint)
        session.commit()
    return user_id, debate_id


@pytest.mark.anyio
async def test_cancel_run_terminalizes_attempt_and_invalidates_execution(monkeypatch):
    user_id, debate_id = _make_user_and_run()
    fake_backend = _FakeBackend()
    tombstones: list[tuple[str, int]] = []

    async def fake_tombstone(run_id: str, epoch: int) -> None:
        tombstones.append((run_id, epoch))

    monkeypatch.setattr(cancel_module, "require_schema_current", lambda _session: None)
    monkeypatch.setattr(cancel_module, "get_sse_backend", lambda: fake_backend)
    monkeypatch.setattr(cancel_module, "_publish_cancel_tombstone", fake_tombstone)

    with session_scope() as session:
        user = session.get(User, user_id)
        result = await cancel_module.cancel_debate_run(
            debate_id,
            session=session,
            current_user=user,
        )

    assert result["status"] == "cancelled"
    assert result["already_cancelled"] is False
    assert tombstones == [(debate_id, 5)]

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        attempt = session.exec(
            cancel_module.select(DebateAttempt).where(DebateAttempt.debate_id == debate_id)
        ).first()
        checkpoint = session.exec(
            cancel_module.select(DebateStageCheckpoint).where(
                DebateStageCheckpoint.debate_id == debate_id
            )
        ).first()
        assert debate.status == "cancelled"
        assert debate.runner_id is None
        assert debate.execution_owner_id is None
        assert debate.lease_expires_at is None
        assert debate.lease_epoch == 5
        assert attempt.status == "cancelled"
        assert checkpoint.status == "invalidated"
        assert checkpoint.owner_id is None
        assert checkpoint.lease_epoch is None

    assert len(fake_backend.events) == 1
    channel, event = fake_backend.events[0]
    assert channel == f"debate:{debate_id}"
    assert event["status"] == "cancelled"
    assert event["reason"] == "cancelled_by_user"


@pytest.mark.anyio
async def test_cancel_run_is_idempotent(monkeypatch):
    user_id, debate_id = _make_user_and_run(status="cancelled")
    fake_backend = _FakeBackend()
    monkeypatch.setattr(cancel_module, "require_schema_current", lambda _session: None)
    monkeypatch.setattr(cancel_module, "get_sse_backend", lambda: fake_backend)

    with session_scope() as session:
        user = session.get(User, user_id)
        result = await cancel_module.cancel_debate_run(
            debate_id,
            session=session,
            current_user=user,
        )

    assert result == {
        "id": debate_id,
        "status": "cancelled",
        "already_cancelled": True,
    }
    assert fake_backend.events == []


@pytest.mark.anyio
async def test_completed_run_cannot_be_cancelled(monkeypatch):
    user_id, debate_id = _make_user_and_run(status="completed")
    monkeypatch.setattr(cancel_module, "require_schema_current", lambda _session: None)

    with session_scope() as session:
        user = session.get(User, user_id)
        with pytest.raises(HTTPException) as exc_info:
            await cancel_module.cancel_debate_run(
                debate_id,
                session=session,
                current_user=user,
            )

    assert exc_info.value.status_code == 409
