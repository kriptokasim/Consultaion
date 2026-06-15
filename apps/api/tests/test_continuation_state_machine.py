import pytest
from models import Debate, User, DebateContinuation
from sqlmodel import Session
from auth import hash_password
from exceptions import ContinuationTransitionError
from services.continuations import transition_continuation_sync, transition_continuation_async


def test_continuation_state_machine_transitions(db_session: Session):
    # Setup user
    user = User(email="sm@example.com", password_hash=hash_password("password"))
    db_session.add(user)
    db_session.commit()

    # Setup debate
    debate = Debate(
        id="sm-debate-1",
        user_id=user.id,
        prompt="Transition prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    # Create continuation
    cont = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="sm-key-1",
        status="requested",
        user_id=user.id,
    )
    db_session.add(cont)
    db_session.commit()

    c_id = str(cont.id)

    # 1. requested -> running should fail if we expect preflight_passed
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, c_id, ["preflight_passed"], "running")

    # 2. Transition requested -> preflight_passed
    res = transition_continuation_sync(db_session, c_id, ["requested"], "preflight_passed")
    assert res.status == "preflight_passed"
    assert res.preflight_passed_at is not None

    # 3. Transition preflight_passed -> dispatched
    res = transition_continuation_sync(db_session, c_id, ["preflight_passed"], "dispatched")
    assert res.status == "dispatched"
    assert res.dispatched_at is not None

    # 4. Transition dispatched -> running
    res = transition_continuation_sync(db_session, c_id, ["dispatched"], "running")
    assert res.status == "running"
    assert res.started_at is not None

    # 5. Transition running -> completed
    res = transition_continuation_sync(db_session, c_id, ["running"], "completed")
    assert res.status == "completed"
    assert res.completed_at is not None

    # 6. Completed -> running should fail
    with pytest.raises(ContinuationTransitionError):
        transition_continuation_sync(db_session, c_id, ["running"], "running")


@pytest.mark.asyncio
async def test_continuation_state_machine_async_transitions(db_session: Session):
    # Setup user
    user = User(email="sm_async@example.com", password_hash=hash_password("password"))
    db_session.add(user)
    db_session.commit()

    # Setup debate
    debate = Debate(
        id="sm-debate-async-1",
        user_id=user.id,
        prompt="Transition prompt async",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    # Create continuation
    cont = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="sm-key-async-1",
        status="requested",
        user_id=user.id,
    )
    db_session.add(cont)
    db_session.commit()

    c_id = str(cont.id)
    db_session.close()

    # Try transition to running expecting dispatched
    with pytest.raises(ContinuationTransitionError):
        await transition_continuation_async(c_id, ["dispatched"], "running")

    # Correct transition: requested -> dispatched (allow this in expected list)
    res = await transition_continuation_async(c_id, ["requested"], "dispatched")
    assert res.status == "dispatched"

    # Correct transition: dispatched -> running
    res = await transition_continuation_async(c_id, ["dispatched"], "running")
    assert res.status == "running"

    # Correct transition: running -> failed
    res = await transition_continuation_async(c_id, ["running"], "failed", failure_code="aborted")
    assert res.status == "failed"
    assert res.failure_code == "aborted"
