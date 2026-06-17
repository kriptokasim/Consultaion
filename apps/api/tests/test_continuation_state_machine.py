import pytest
from models import Debate, User, DebateContinuation
from sqlmodel import Session
from auth import hash_password
from exceptions import ContinuationTransitionError
from services.continuations import (
    transition_continuation_sync,
    transition_continuation_async,
    ALLOWED_CONTINUATION_TRANSITIONS,
)


def _create_debate_and_continuation(db_session: Session, debate_id: str, cont_key: str):
    user = User(email=f"sm_{debate_id}@example.com", password_hash=hash_password("password"))
    db_session.add(user)
    db_session.commit()

    debate = Debate(
        id=debate_id,
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    cont = DebateContinuation(
        debate_id=debate.id,
        idempotency_key=cont_key,
        status="requested",
        user_id=user.id,
    )
    db_session.add(cont)
    db_session.commit()
    return user, debate, cont


def test_requested_to_preflight_passed(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-1", "key-1")
    res = transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    assert res.status == "preflight_passed"
    assert res.preflight_passed_at is not None


def test_preflight_passed_to_dispatched(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-2", "key-2")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    res = transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    assert res.status == "dispatched"
    assert res.dispatched_at is not None


def test_dispatched_to_running(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-3", "key-3")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    res = transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    assert res.status == "running"
    assert res.started_at is not None


def test_running_to_paused(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-4", "key-4")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    res = transition_continuation_sync(db_session, cont.id, ["running"], "paused")
    assert res.status == "paused"
    assert res.paused_at is not None


def test_running_to_completed(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-5", "key-5")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    res = transition_continuation_sync(db_session, cont.id, ["running"], "completed")
    assert res.status == "completed"
    assert res.completed_at is not None


def test_running_to_failed(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-6", "key-6")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    res = transition_continuation_sync(db_session, cont.id, ["running"], "failed", failure_code="test_error")
    assert res.status == "failed"
    assert res.failed_at is not None
    assert res.failure_code == "test_error"


def test_paused_cannot_transition(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-7", "key-7")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    transition_continuation_sync(db_session, cont.id, ["running"], "paused")
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["paused"], "running")
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["paused"], "completed")


def test_completed_cannot_transition(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-8", "key-8")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    transition_continuation_sync(db_session, cont.id, ["running"], "completed")
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["completed"], "running")


def test_failed_cannot_transition_to_non_requested(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-9", "key-9")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    transition_continuation_sync(db_session, cont.id, ["running"], "failed")
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["failed"], "running")


def test_failed_cannot_transition_to_requested_or_preflight_passed(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-10", "key-10")
    transition_continuation_sync(db_session, cont.id, ["requested"], "failed")
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["failed"], "requested")
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["failed"], "preflight_passed")



def test_normal_non_resume_run_never_modifies_continuation(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-12", "key-12")
    assert cont.status == "requested"
    assert cont.started_at is None
    assert cont.completed_at is None


def test_resume_pause_writes_paused(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-13", "key-13")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    res = transition_continuation_sync(db_session, cont.id, ["running"], "paused")
    assert res.status == "paused"
    assert res.paused_at is not None
    assert res.completed_at is None


def test_two_workers_cannot_both_transition_dispatched_to_running(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-14", "key-14")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    res1 = transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    assert res1.status == "running"
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")


def test_transition_conflict_not_silently_swallowed(db_session: Session):
    user, debate, cont = _create_debate_and_continuation(db_session, "sm-15", "key-15")
    transition_continuation_sync(db_session, cont.id, ["requested"], "preflight_passed")
    transition_continuation_sync(db_session, cont.id, ["preflight_passed"], "dispatched")
    transition_continuation_sync(db_session, cont.id, ["dispatched"], "running")
    transition_continuation_sync(db_session, cont.id, ["running"], "completed")
    with pytest.raises(ContinuationTransitionError) as exc_info:
        transition_continuation_sync(db_session, cont.id, ["running"], "failed")
    assert "not in expected" in str(exc_info.value) or "Invalid" in str(exc_info.value)


def test_missing_continuation_id_does_not_update_another_record(db_session: Session):
    user, debate, cont1 = _create_debate_and_continuation(db_session, "sm-16a", "key-16a")
    cont2 = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="key-16b",
        status="requested",
        user_id=user.id,
    )
    db_session.add(cont2)
    db_session.commit()
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, "nonexistent-id", ["requested"], "running")
    db_session.refresh(cont2)
    assert cont2.status == "requested"


def test_transition_map_completeness():
    expected_statuses = {
        "requested", "preflight_passed", "dispatched", "running",
        "paused", "completed", "failed", "cancelled",
    }
    assert set(ALLOWED_CONTINUATION_TRANSITIONS.keys()) == expected_statuses
    for status in ["paused", "completed", "cancelled", "failed"]:
        assert ALLOWED_CONTINUATION_TRANSITIONS[status] == set(), f"{status} should be terminal"



@pytest.mark.anyio
async def test_async_transitions_with_paused(db_session: Session):
    user = User(email="sm_async_paused@example.com", password_hash=hash_password("password"))
    db_session.add(user)
    db_session.commit()

    debate = Debate(id="sm-debate-async-paused", user_id=user.id, prompt="Async paused test", status="perspectives_ready")
    db_session.add(debate)
    db_session.commit()

    cont = DebateContinuation(debate_id=debate.id, idempotency_key="key-async-paused", status="requested", user_id=user.id)
    db_session.add(cont)
    db_session.commit()
    c_id = cont.id
    db_session.close()

    await transition_continuation_async(c_id, ["requested"], "preflight_passed")
    await transition_continuation_async(c_id, ["preflight_passed"], "dispatched")
    await transition_continuation_async(c_id, ["dispatched"], "running")
    res = await transition_continuation_async(c_id, ["running"], "paused")
    assert res.status == "paused"
    assert res.paused_at is not None
