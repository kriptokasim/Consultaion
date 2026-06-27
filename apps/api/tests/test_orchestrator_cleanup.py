import pytest
from datetime import datetime, timedelta, timezone
from sqlmodel import Session
from models import Debate
from orchestrator_cleanup import cleanup_stale_debates

@pytest.mark.asyncio
async def test_lease_timeout_retries_exceeded(db_session: Session):
    now = datetime.now(timezone.utc)
    
    # Create a running debate with expired lease and max retries
    stale_debate = Debate(
        id="test_stale_lease",
        status="running",
        run_attempt=3,
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=10),
        lease_expires_at=now - timedelta(minutes=5),
        user_id="test_user",
        prompt="test prompt",
        mode="arena"
    )
    db_session.add(stale_debate)
    db_session.commit()
    
    failed, degraded = await cleanup_stale_debates()
    
    db_session.refresh(stale_debate)
    
    assert stale_debate.status == "failed"
    assert stale_debate.final_meta is not None
    assert stale_debate.final_meta["stale_cleanup"]["reason"] == "lease_timeout_retries_exceeded"
    assert stale_debate.final_meta["stale_cleanup"]["failure_code"] == "lease_timeout_retries_exceeded"
    assert failed == 1
    assert degraded == 0
