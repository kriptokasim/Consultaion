import pytest
from models import Debate, User, DebateContinuation
from sqlmodel import select
from datetime import datetime, timezone
from auth import hash_password
from services.continuations import update_continuation_sync, update_continuation_async


def test_update_continuation_sync(db_session):
    # Setup test user
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
        user_id=user.id
    )
    db_session.add(continuation)
    db_session.commit()

    # 1. Update status to running
    res = update_continuation_sync(db_session, debate.id, "running")
    assert res is not None
    assert res.status == "running"
    assert res.started_at is not None

    # 2. Update status to completed
    res = update_continuation_sync(db_session, debate.id, "completed")
    assert res is not None
    assert res.status == "completed"
    assert res.completed_at is not None

    # 3. Create another continuation and test failed state
    continuation2 = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="sync-key-456",
        status="requested",
        user_id=user.id
    )
    db_session.add(continuation2)
    db_session.commit()

    res = update_continuation_sync(
        db_session,
        debate.id,
        "failed",
        failure_code="test_error",
        failure_detail_safe="Test safe failure detail"
    )
    assert res is not None
    assert res.status == "failed"
    assert res.failed_at is not None
    assert res.failure_code == "test_error"
    assert res.failure_detail_safe == "Test safe failure detail"


@pytest.mark.asyncio
async def test_update_continuation_async(db_session):
    # Setup test user
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
        user_id=user.id
    )
    db_session.add(continuation)
    db_session.commit()

    # Cache debate ID as standard string to prevent DetachedInstanceError
    debate_id = str(debate.id)
    db_session.close()

    # 1. Update status to running
    res = await update_continuation_async(debate_id, "running")
    assert res is not None
    assert res.status == "running"
    assert res.started_at is not None

    # 2. Update status to failed
    res = await update_continuation_async(
        debate_id,
        "failed",
        failure_code="async_error",
        failure_detail_safe="Async safe failure detail"
    )
    assert res is not None
    assert res.status == "failed"
    assert res.failed_at is not None
    assert res.failure_code == "async_error"
    assert res.failure_detail_safe == "Async safe failure detail"
