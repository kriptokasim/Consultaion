from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from models import Debate
from sqlmodel import Session

from tests.utils import ensure_user


@pytest.mark.asyncio
async def test_lease_timeout_retries_exceeded(db_session: Session):
    """An expired lease past its recovery budget is terminalized, not redispatched.

    The budget lives in final_meta.recovery_dispatch for the current logical
    attempt; run_attempt alone is not a crash-retry counter.
    """
    import orchestrator_cleanup
    from cleanup_recovery_guard import _MAX_RECOVERY_DISPATCHES, install_cleanup_recovery_guard

    install_cleanup_recovery_guard()
    now = datetime.now(timezone.utc)
    ensure_user(db_session, "test_user")
    stale_debate = Debate(
        id="test_stale_lease",
        status="running",
        run_attempt=3,
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=10),
        lease_expires_at=now - timedelta(minutes=5),
        user_id="test_user",
        prompt="test prompt",
        mode="arena",
        final_meta={
            "recovery_dispatch": {"attempt_number": 3, "count": _MAX_RECOVERY_DISPATCHES}
        },
    )
    db_session.add(stale_debate)
    db_session.commit()

    with patch("debate_dispatch.dispatch_debate_run", new_callable=AsyncMock) as dispatch:
        failed, degraded = await orchestrator_cleanup.cleanup_stale_debates()

    dispatch.assert_not_awaited()
    db_session.refresh(stale_debate)

    assert stale_debate.status == "failed"
    assert stale_debate.final_meta is not None
    assert stale_debate.final_meta["stale_cleanup"]["reason"] == "lease_expired"
    assert stale_debate.final_meta["stale_cleanup"]["failure_code"] == "recovery_dispatches_exhausted"
    assert failed == 1
    assert degraded == 0
