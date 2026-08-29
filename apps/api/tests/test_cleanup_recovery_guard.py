from datetime import timedelta

import pytest


def _seed_attempt(db_session, debate, *, status="running"):
    from models import DebateAttempt

    attempt_number = max(int(debate.run_attempt or 0), 1)
    attempt = DebateAttempt(
        debate_id=debate.id,
        attempt_number=attempt_number,
        status=status,
        model_id=debate.model_id,
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_live_lease_is_never_cleaned_for_old_checkpoint(db_session):
    import cleanup_recovery_guard as guard
    from models import Debate, DebateCheckpoint, utcnow

    now = utcnow()
    debate = Debate(
        id="live-owner",
        prompt="test",
        status="running",
        run_attempt=1,
        runner_id="owner-a",
        execution_owner_id="owner-a",
        lease_epoch=4,
        lease_expires_at=now + timedelta(minutes=2),
        last_heartbeat_at=now,
        updated_at=now - timedelta(hours=3),
    )
    db_session.add(debate)
    db_session.add(
        DebateCheckpoint(
            debate_id=debate.id,
            step="synthesis",
            status="running",
            last_checkpoint_at=now - timedelta(hours=3),
            last_event_at=now - timedelta(hours=3),
        )
    )
    db_session.commit()

    assert guard._classify_candidate(db_session, debate, now) is None


def test_expired_initial_attempt_recovery_preserves_attempt_and_staged_pause(db_session):
    import cleanup_recovery_guard as guard
    from models import Debate, utcnow

    now = utcnow()
    debate = Debate(
        id="expired-initial",
        prompt="test",
        status="running",
        mode="arena",
        run_attempt=1,
        runner_id="dead-owner",
        execution_owner_id="dead-owner",
        lease_epoch=7,
        lease_expires_at=now - timedelta(seconds=5),
        updated_at=now,
    )
    db_session.add(debate)
    db_session.commit()
    _seed_attempt(db_session, debate)

    prepared = guard._prepare_recovery(
        debate.id,
        "lease_expired",
        5,
        now,
    )

    assert prepared["action"] == "dispatch"
    assert prepared["resume"] is False
    assert prepared["continuation_id"] is None
    db_session.expire_all()
    persisted = db_session.get(Debate, debate.id)
    assert persisted.status == "scheduled"
    assert persisted.run_attempt == 1
    assert persisted.lease_epoch == 7
    assert persisted.runner_id is None
    assert persisted.execution_owner_id is None


def test_expired_full_retry_recovery_keeps_retry_resume_semantics(db_session):
    import cleanup_recovery_guard as guard
    from models import Debate, utcnow

    now = utcnow()
    debate = Debate(
        id="expired-retry",
        prompt="test",
        status="running",
        mode="arena",
        run_attempt=2,
        runner_id="dead-owner",
        execution_owner_id="dead-owner",
        lease_epoch=8,
        lease_expires_at=now - timedelta(seconds=5),
        updated_at=now,
    )
    db_session.add(debate)
    db_session.commit()
    _seed_attempt(db_session, debate)

    prepared = guard._prepare_recovery(debate.id, "lease_expired", 5, now)

    assert prepared["action"] == "dispatch"
    assert prepared["resume"] is True
    db_session.expire_all()
    assert db_session.get(Debate, debate.id).run_attempt == 2


def test_expired_continuation_recovery_preserves_continuation_identity(db_session):
    import cleanup_recovery_guard as guard
    from models import Debate, DebateContinuation, utcnow

    now = utcnow()
    debate = Debate(
        id="expired-continuation",
        prompt="test",
        status="running",
        mode="arena",
        run_attempt=1,
        runner_id="dead-owner",
        execution_owner_id="dead-owner",
        lease_epoch=2,
        lease_expires_at=now - timedelta(seconds=5),
        updated_at=now,
    )
    continuation = DebateContinuation(
        id="continuation-1",
        debate_id=debate.id,
        idempotency_key="continuation-key",
        status="running",
        updated_at=now,
    )
    db_session.add(debate)
    db_session.add(continuation)
    db_session.commit()
    _seed_attempt(db_session, debate)

    prepared = guard._prepare_recovery(debate.id, "lease_expired", 5, now)

    assert prepared["action"] == "dispatch"
    assert prepared["resume"] is True
    assert prepared["continuation_id"] == continuation.id


def test_recovery_exhaustion_uses_canonical_failed_not_degraded(db_session):
    import cleanup_recovery_guard as guard
    from models import Debate, Message, utcnow

    now = utcnow()
    debate = Debate(
        id="recovery-exhausted",
        prompt="test",
        status="running",
        run_attempt=1,
        runner_id="dead-owner",
        execution_owner_id="dead-owner",
        lease_epoch=9,
        lease_expires_at=now - timedelta(seconds=10),
        updated_at=now,
        final_meta={
            "recovery_dispatch": {
                "attempt_number": 1,
                "count": guard._MAX_RECOVERY_DISPATCHES,
            }
        },
    )
    db_session.add(debate)
    db_session.commit()
    attempt = _seed_attempt(db_session, debate)
    db_session.add(
        Message(
            debate_id=debate.id,
            attempt_id=attempt.id,
            round_index=0,
            role="arena_response",
            persona="model-a",
            content="partial durable output",
        )
    )
    db_session.commit()

    prepared = guard._prepare_recovery(debate.id, "lease_expired", 10, now)

    assert prepared["action"] == "failed"
    assert prepared["partial_output_available"] is True
    db_session.expire_all()
    persisted = db_session.get(Debate, debate.id)
    assert persisted.status == "failed"
    assert persisted.final_meta["stale_cleanup"]["partial_output_available"] is True
    assert db_session.get(type(attempt), attempt.id).status == "failed"


def test_manual_queued_runs_are_not_expired_by_cleanup(db_session, monkeypatch):
    import cleanup_recovery_guard as guard
    from config import settings
    from models import Debate, utcnow

    monkeypatch.setattr(settings, "DISABLE_AUTORUN", True)
    now = utcnow()
    debate = Debate(
        id="manual-queued",
        prompt="test",
        status="queued",
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
    )
    db_session.add(debate)
    db_session.commit()

    assert guard._classify_candidate(db_session, debate, now) is None


@pytest.mark.anyio
async def test_unfenced_prelease_start_notice_is_suppressed():
    from sse_execution_guard import ExecutionFencedSSEBackend

    class Backend:
        def __init__(self):
            self.events = []

        async def publish(self, channel_id, event):
            self.events.append((channel_id, event))

    backend = Backend()
    guarded = ExecutionFencedSSEBackend(backend)
    await guarded.publish(
        "debate:duplicate-task",
        {
            "type": "notice",
            "round": 0,
            "payload": {"message": "Debate run started", "note": "plan"},
        },
    )

    assert backend.events == []
