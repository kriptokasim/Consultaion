import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from database import session_scope
from models import Debate
from orchestrator import _heartbeat, _release_lease, _try_acquire_lease
from orchestrator_cleanup import cleanup_stale_debates

# Use a test-specific runner ID
TEST_RUNNER_A = "runner-a"
TEST_RUNNER_B = "runner-b"

def ensure_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def create_test_debate(session, debate_id="test-debate-lease"):
    # Clean up existing
    existing = session.get(Debate, debate_id)
    if existing:
        session.delete(existing)
        session.commit()
        
    debate = Debate(
        id=debate_id,
        prompt="Test Prompt",
        status="queued",
        user_id="test-user"
    )
    session.add(debate)
    session.commit()
    return debate

@pytest.mark.asyncio
async def test_lease_acquisition():
    with session_scope() as session:
        debate = create_test_debate(session, "test-acq")
        debate_id = debate.id
        
    # Attempt 1: Success
    assert await _try_acquire_lease(debate_id, TEST_RUNNER_A, lease_seconds=10) is True
    
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        assert debate.runner_id == TEST_RUNNER_A
        assert debate.status == "running"
        expiry = ensure_aware(debate.lease_expires_at)
        assert expiry > datetime.now(timezone.utc)

    # Attempt 2: Failure (Locked by A)
    assert await _try_acquire_lease(debate_id, TEST_RUNNER_B, lease_seconds=10) is False
    
    # Attempt 3: Success (Re-acquire by A)
    assert await _try_acquire_lease(debate_id, TEST_RUNNER_A, lease_seconds=10) is True

@pytest.mark.asyncio
async def test_lease_expiration_takeover():
    debate_id = "test-expire"
    with session_scope() as session:
        create_test_debate(session, debate_id)
        debate = session.get(Debate, debate_id)
        # Manually expire lease
        debate.runner_id = TEST_RUNNER_A
        debate.status = "running"
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(debate)
        session.commit()
        
    # Attempt 4: Success (Takeover by B because expired)
    assert await _try_acquire_lease(debate_id, TEST_RUNNER_B, lease_seconds=10) is True
    
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        assert debate.runner_id == TEST_RUNNER_B

@pytest.mark.asyncio
async def test_heartbeat_updates():
    debate_id = "test-heartbeat"
    with session_scope() as session:
        create_test_debate(session, debate_id)
        await _try_acquire_lease(debate_id, TEST_RUNNER_B, lease_seconds=10)
        debate = session.get(Debate, debate_id)
        old_expiry = ensure_aware(debate.lease_expires_at)
        
    # Wait a bit
    await asyncio.sleep(0.1)
    
    # Heartbeat
    await _heartbeat(debate_id, TEST_RUNNER_B, lease_seconds=20)
    
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        new_expiry = ensure_aware(debate.lease_expires_at)
        assert new_expiry > old_expiry
        assert (new_expiry - datetime.now(timezone.utc)).total_seconds() > 15

@pytest.mark.asyncio
async def test_release_lease():
    debate_id = "test-release"
    with session_scope() as session:
        create_test_debate(session, debate_id)
        await _try_acquire_lease(debate_id, TEST_RUNNER_B, lease_seconds=10)
        
    await _release_lease(debate_id, TEST_RUNNER_B)
    
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        assert debate.runner_id is None
        assert debate.lease_expires_at is None

@pytest.mark.asyncio
async def test_cleanup_requeue():
    debate_id = "test-debate-requeue"
    runner_id = "crashed-runner"
    
    with session_scope() as session:
        # Clean up if exists
        existing = session.get(Debate, debate_id)
        if existing:
            session.delete(existing)
        session.commit()

        debate = Debate(
            id=debate_id,
            prompt="Stale",
            status="running",
            runner_id=runner_id,
            lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            run_attempt=0,
            user_id="test-user"
        )
        session.add(debate)
        session.commit()
    
    # Run cleanup
    with patch("orchestrator_cleanup.settings") as mock_settings:
        # Mock settings so existing checks don't interfere (or ensure they align)
        mock_settings.DEBATE_STALE_RUNNING_SECONDS = 3600
        mock_settings.DEBATE_STALE_QUEUED_SECONDS = 3600
        
        await cleanup_stale_debates()
    
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        # Should be requeued
        assert debate.status == "queued"
        assert debate.runner_id is None
        assert debate.lease_expires_at is None
        
        # Test retry exhaustion
        debate.status = "running"
        debate.runner_id = runner_id
        debate.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        debate.run_attempt = 3 # Limit reached
        session.add(debate)
        session.commit()
        
    # Run cleanup again
    with patch("orchestrator_cleanup.settings") as mock_settings:
         mock_settings.DEBATE_STALE_RUNNING_SECONDS = 3600
         mock_settings.DEBATE_STALE_QUEUED_SECONDS = 3600
         await cleanup_stale_debates()

    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        assert debate.status == "failed"
