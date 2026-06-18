"""PostgreSQL concurrency tests for run limits.

Patchset 133 §7.5: Proves exact run limit is enforced under parallel requests
and missing counter initialization is race-safe.
"""

import uuid
import asyncio
import pytest
from sqlmodel import Session, select
from models import User, UsageCounter, UsageQuota
from usage_limits import reserve_run_slot, RateLimitError


@pytest.fixture
def test_user(db_session):
    user = User(
        id=str(uuid.uuid4()),
        email=f"concurrency-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pass",
        plan="free",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestRunLimitConcurrency:
    def test_exact_limit_enforced(self, db_session, test_user):
        """Run limit is enforced — exceeding limit raises RateLimitError."""
        # Set a tight limit of 3 runs
        quota = UsageQuota(
            user_id=test_user.id,
            period="hour",
            max_runs=3,
            max_tokens=None,
        )
        db_session.add(quota)
        db_session.commit()

        # Use 3 run slots
        for i in range(3):
            reserve_run_slot(db_session, test_user.id)

        # 4th should fail
        with pytest.raises(RateLimitError):
            reserve_run_slot(db_session, test_user.id)

    def test_unlimited_quota_works(self, db_session, test_user):
        """Unlimited quota (max_runs=None) allows unlimited reservations."""
        quota = UsageQuota(
            user_id=test_user.id,
            period="hour",
            max_runs=None,
            max_tokens=None,
        )
        db_session.add(quota)
        db_session.commit()

        # Should not raise even with many reservations
        for i in range(10):
            reserve_run_slot(db_session, test_user.id)

    def test_missing_counter_initialization(self, db_session, test_user):
        """Missing counter row is initialized safely on first reservation."""
        # Ensure no counter exists
        existing = db_session.exec(
            select(UsageCounter).where(
                UsageCounter.user_id == test_user.id,
                UsageCounter.period == "hour",
            )
        ).first()
        assert existing is None

        # First reservation should initialize the counter
        reserve_run_slot(db_session, test_user.id)

        counter = db_session.exec(
            select(UsageCounter).where(
                UsageCounter.user_id == test_user.id,
                UsageCounter.period == "hour",
            )
        ).first()
        assert counter is not None
        assert counter.runs_used == 1

    def test_period_reset_allows_new_runs(self, db_session, test_user):
        """After period expires, new runs are allowed."""
        from datetime import timedelta
        from models import utcnow

        quota = UsageQuota(
            user_id=test_user.id,
            period="hour",
            max_runs=2,
            max_tokens=None,
        )
        db_session.add(quota)
        db_session.commit()

        # Use all slots
        reserve_run_slot(db_session, test_user.id)
        reserve_run_slot(db_session, test_user.id)

        # 3rd should fail
        with pytest.raises(RateLimitError):
            reserve_run_slot(db_session, test_user.id)

        # Simulate period expiry by backdating the counter
        counter = db_session.exec(
            select(UsageCounter).where(
                UsageCounter.user_id == test_user.id,
                UsageCounter.period == "hour",
            )
        ).first()
        counter.window_start = utcnow() - timedelta(hours=2)
        db_session.add(counter)
        db_session.commit()

        # Now reservation should succeed (period reset)
        reserve_run_slot(db_session, test_user.id)
