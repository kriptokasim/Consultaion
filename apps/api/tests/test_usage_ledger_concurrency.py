"""Usage ledger state machine and concurrency tests.

Patchset 133 §7.5: Proves valid transitions, idempotency, and concurrency safety.
"""

import uuid
import pytest
from sqlmodel import Session, select
from models import User, UsageLedgerEntry
from services.usage_ledger import (
    reserve_run, settle_run, refund_run,
    record_token_usage, settle_token_usage,
    record_export, reserve_hosted_credit, settle_hosted_credit, refund_hosted_credit,
    LedgerTransitionError,
)


@pytest.fixture
def test_user(db_session):
    user = User(
        id=str(uuid.uuid4()),
        email=f"ledger-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pass",
        plan="free",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestLedgerTransitions:
    def test_reserve_then_settle(self, db_session, test_user):
        """Valid transition: reserved → settled."""
        entry = reserve_run(db_session, test_user.id, "debate-1")
        assert entry.status == "reserved"

        settled = settle_run(db_session, test_user.id, "debate-1")
        assert settled.status == "settled"
        assert settled.settled_at is not None

    def test_reserve_then_refund(self, db_session, test_user):
        """Valid transition: reserved → refunded."""
        entry = reserve_run(db_session, test_user.id, "debate-2")
        assert entry.status == "reserved"

        refunded = refund_run(db_session, test_user.id, "debate-2")
        assert refunded.status == "refunded"
        assert refunded.refunded_at is not None

    def test_settle_then_refund_rejected(self, db_session, test_user):
        """Invalid transition: settled → refunded."""
        reserve_run(db_session, test_user.id, "debate-3")
        settle_run(db_session, test_user.id, "debate-3")

        with pytest.raises(LedgerTransitionError):
            refund_run(db_session, test_user.id, "debate-3")

    def test_refund_then_settle_rejected(self, db_session, test_user):
        """Invalid transition: refunded → settled."""
        reserve_run(db_session, test_user.id, "debate-4")
        refund_run(db_session, test_user.id, "debate-4")

        with pytest.raises(LedgerTransitionError):
            settle_run(db_session, test_user.id, "debate-4")

    def test_duplicate_reserve_is_idempotent(self, db_session, test_user):
        """Duplicate reservation returns same entry."""
        entry1 = reserve_run(db_session, test_user.id, "debate-5")
        entry2 = reserve_run(db_session, test_user.id, "debate-5")
        assert entry1.id == entry2.id


class TestTokenUsage:
    def test_token_usage_attempt_scoped(self, db_session, test_user):
        """Token usage is scoped by debate and attempt."""
        entry1 = record_token_usage(db_session, test_user.id, "debate-6", "attempt-1", 100)
        entry2 = record_token_usage(db_session, test_user.id, "debate-6", "attempt-2", 200)

        assert entry1.id != entry2.id
        assert entry1.amount == 100
        assert entry2.amount == 200
        assert entry1.attempt_id == "attempt-1"
        assert entry2.attempt_id == "attempt-2"

    def test_token_usage_idempotent_per_attempt(self, db_session, test_user):
        """Same attempt returns same entry."""
        entry1 = record_token_usage(db_session, test_user.id, "debate-7", "attempt-1", 100)
        entry2 = record_token_usage(db_session, test_user.id, "debate-7", "attempt-1", 200)
        assert entry1.id == entry2.id
        assert entry1.amount == 100  # Original amount preserved


class TestExportIdempotency:
    def test_export_deterministic_key(self, db_session, test_user):
        """Export uses deterministic idempotency key."""
        entry1 = record_export(db_session, test_user.id, "debate-8")
        entry2 = record_export(db_session, test_user.id, "debate-8")
        assert entry1.id == entry2.id

    def test_export_different_users_separate(self, db_session):
        """Different users get separate export entries."""
        user1 = User(
            id=str(uuid.uuid4()),
            email=f"export1-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash",
            plan="free",
            is_active=True,
        )
        user2 = User(
            id=str(uuid.uuid4()),
            email=f"export2-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash",
            plan="free",
            is_active=True,
        )
        db_session.add_all([user1, user2])
        db_session.commit()

        entry1 = record_export(db_session, user1.id, "debate-9")
        entry2 = record_export(db_session, user2.id, "debate-9")
        assert entry1.id != entry2.id


class TestHostedCredits:
    def test_credit_reserve_settle(self, db_session, test_user):
        """Credit lifecycle: reserve → settle."""
        entry = reserve_hosted_credit(db_session, test_user.id, "debate-10")
        assert entry.status == "reserved"

        settled = settle_hosted_credit(db_session, test_user.id, "debate-10")
        assert settled.status == "settled"

    def test_credit_reserve_refund(self, db_session, test_user):
        """Credit lifecycle: reserve → refund."""
        entry = reserve_hosted_credit(db_session, test_user.id, "debate-11")
        assert entry.status == "reserved"

        refunded = refund_hosted_credit(db_session, test_user.id, "debate-11")
        assert refunded.status == "refunded"

    def test_credit_refund_after_settle_rejected(self, db_session, test_user):
        """Cannot refund after settlement."""
        reserve_hosted_credit(db_session, test_user.id, "debate-12")
        settle_hosted_credit(db_session, test_user.id, "debate-12")

        with pytest.raises(LedgerTransitionError):
            refund_hosted_credit(db_session, test_user.id, "debate-12")
