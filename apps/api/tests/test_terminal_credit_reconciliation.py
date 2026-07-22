"""Durable hosted-credit terminal settlement regression tests."""

from __future__ import annotations

from datetime import datetime, timezone

from billing.reconciliation import reconcile_terminal_hosted_credit_reservations
from models import Debate, DebateContinuation, UsageLedgerEntry, User


def _user(user_id: str) -> User:
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="...",
        hosted_credits_limit=10,
        hosted_credits_used=1,
    )


def test_reconciler_consumes_completed_initial_reservation(db_session):
    user = _user("credit-reconcile-completed")
    reservation_id = "reservation-completed"
    debate = Debate(
        id="debate-credit-completed",
        user_id=user.id,
        prompt="done",
        status="completed",
        credit_reservation_id=reservation_id,
    )
    reservation = UsageLedgerEntry(
        id=reservation_id,
        user_id=user.id,
        kind="credit_reservation",
        status="reserved",
        idempotency_key="credit-reconcile-completed",
        amount=1,
        debate_id=debate.id,
        meta={"run_attempt": 1, "continuation_id": None},
    )
    db_session.add_all([user, debate, reservation])
    db_session.commit()

    summary = reconcile_terminal_hosted_credit_reservations(
        db_session,
        older_than=datetime.now(timezone.utc),
    )

    db_session.refresh(reservation)
    db_session.refresh(user)
    assert summary["settled"] == 1
    assert reservation.status == "settled"
    assert reservation.settled_at is not None
    assert user.hosted_credits_used == 1


def test_reconciler_uses_continuation_status_and_refunds_exact_reservation(db_session):
    user = _user("credit-reconcile-continuation")
    reservation_id = "reservation-continuation-failed"
    debate = Debate(
        id="debate-credit-continuation",
        user_id=user.id,
        prompt="global debate later completed",
        status="completed",
    )
    continuation = DebateContinuation(
        id="continuation-credit-failed",
        debate_id=debate.id,
        user_id=user.id,
        idempotency_key="continuation-credit-failed-key",
        status="failed",
        credit_reservation_id=reservation_id,
    )
    reservation = UsageLedgerEntry(
        id=reservation_id,
        user_id=user.id,
        kind="credit_reservation",
        status="reserved",
        idempotency_key="credit-reconcile-continuation",
        amount=1,
        debate_id=debate.id,
        meta={"run_attempt": 2, "continuation_id": continuation.id},
    )
    db_session.add_all([user, debate, continuation, reservation])
    db_session.commit()

    summary = reconcile_terminal_hosted_credit_reservations(
        db_session,
        older_than=datetime.now(timezone.utc),
    )

    db_session.refresh(reservation)
    db_session.refresh(user)
    assert summary["refunded"] == 1
    assert reservation.status == "refunded"
    assert reservation.refunded_at is not None
    assert user.hosted_credits_used == 0


def test_reconciler_quarantines_ambiguous_reservation_without_counter_change(db_session):
    user = _user("credit-reconcile-ambiguous")
    debate = Debate(
        id="debate-credit-ambiguous",
        user_id=user.id,
        prompt="ambiguous historical row",
        status="failed",
        credit_reservation_id="different-reservation",
    )
    reservation = UsageLedgerEntry(
        id="ambiguous-reservation",
        user_id=user.id,
        kind="credit_reservation",
        status="reserved",
        idempotency_key="credit-reconcile-ambiguous",
        amount=1,
        debate_id=debate.id,
        meta=None,
    )
    db_session.add_all([user, debate, reservation])
    db_session.commit()

    summary = reconcile_terminal_hosted_credit_reservations(
        db_session,
        older_than=datetime.now(timezone.utc),
    )

    db_session.refresh(reservation)
    db_session.refresh(user)
    assert summary["quarantined"] == 1
    assert reservation.status == "reconciliation_pending"
    assert user.hosted_credits_used == 1
