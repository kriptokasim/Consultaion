import pytest
from models import Debate, User, DebateContinuation
from sqlmodel import select
from datetime import datetime, timezone
from auth import hash_password
from exceptions import ContinuationTransitionError
from services.continuations import transition_continuation_sync, transition_continuation_async


def test_transition_continuation_sync(db_session):
    user = User(email="normal@example.com", password_hash=hash_password("password"))
    db_session.add(user)
    db_session.commit()

    debate = Debate(
        id="test-continuation-sync-debate",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    continuation = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="sync-key-123",
        status="requested",
        user_id=user.id,
    )
    db_session.add(continuation)
    db_session.commit()

    continuation_id = str(continuation.id)

    res = transition_continuation_sync(db_session, continuation_id, ["requested"], "preflight_passed")
    assert res.status == "preflight_passed"
    assert res.preflight_passed_at is not None

    res = transition_continuation_sync(db_session, continuation_id, ["preflight_passed"], "dispatched")
    assert res.status == "dispatched"

    res = transition_continuation_sync(db_session, continuation_id, ["dispatched"], "running")
    assert res.status == "running"
    assert res.started_at is not None

    res = transition_continuation_sync(db_session, continuation_id, ["running"], "completed")
    assert res.status == "completed"
    assert res.completed_at is not None

    continuation2 = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="sync-key-456",
        status="requested",
        user_id=user.id,
    )
    db_session.add(continuation2)
    db_session.commit()

    continuation2_id = str(continuation2.id)

    res = transition_continuation_sync(
        db_session,
        continuation2_id,
        ["requested"],
        "failed",
        failure_code="test_error",
        failure_detail_safe="Test safe failure detail",
    )
    assert res.status == "failed"
    assert res.failed_at is not None
    assert res.failure_code == "test_error"
    assert res.failure_detail_safe == "Test safe failure detail"

    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, continuation2_id, ["running"], "completed")

    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, "non-existent-id", ["requested"], "running")


def test_transition_validates_canonical_map(db_session):
    user = User(email="map@example.com", password_hash=hash_password("password"))
    db_session.add(user)
    db_session.commit()

    debate = Debate(id="test-map-debate", user_id=user.id, prompt="Map test", status="perspectives_ready")
    db_session.add(debate)
    db_session.commit()

    cont = DebateContinuation(debate_id=debate.id, idempotency_key="map-key", status="requested", user_id=user.id)
    db_session.add(cont)
    db_session.commit()

    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["requested"], "running")


@pytest.mark.anyio
async def test_transition_continuation_async(db_session):
    user = User(email="normal@example.com", password_hash=hash_password("password"))
    db_session.add(user)
    db_session.commit()

    debate = Debate(
        id="test-continuation-async-debate",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    continuation = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="async-key-123",
        status="requested",
        user_id=user.id,
    )
    db_session.add(continuation)
    db_session.commit()

    continuation_id = str(continuation.id)
    db_session.close()

    res = await transition_continuation_async(continuation_id, ["requested"], "preflight_passed")
    assert res.status == "preflight_passed"

    res = await transition_continuation_async(continuation_id, ["preflight_passed"], "dispatched")
    assert res.status == "dispatched"

    res = await transition_continuation_async(continuation_id, ["dispatched"], "running")
    assert res.status == "running"
    assert res.started_at is not None

    res = await transition_continuation_async(
        continuation_id,
        ["running"],
        "failed",
        failure_code="async_error",
        failure_detail_safe="Async safe failure detail",
    )
    assert res.status == "failed"
    assert res.failure_code == "async_error"
    assert res.failure_detail_safe == "Async safe failure detail"

    with pytest.raises(ContinuationTransitionError):
        await transition_continuation_async(continuation_id, ["requested"], "running")
