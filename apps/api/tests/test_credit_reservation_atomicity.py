"""Regression tests for atomic hosted-credit reservation.

The credit counter used to be incremented with a read-check-write sequence,
which allowed two concurrent requests to both pass the exhaustion check and
double-spend the user's final free credit. Reservation is now an atomic
conditional UPDATE (``used < limit``); these tests pin that behavior.
"""

import uuid

import pytest
from billing.service import consume_hosted_credit, refund_hosted_credit, reserve_hosted_credit
from exceptions import ValidationError
from models import User
from sqlmodel import Session


def _make_free_user(db: Session, *, limit: int, used: int) -> User:
    user = User(
        email=f"credits_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        plan="free",
        hosted_credits_limit=limit,
        hosted_credits_used=used,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_reserve_increments_counter(db_session: Session):
    user = _make_free_user(db_session, limit=5, used=4)
    reserve_hosted_credit(db_session, user.id)
    db_session.commit()
    db_session.refresh(user)
    assert user.hosted_credits_used == 5


def test_reserve_raises_when_exhausted(db_session: Session):
    user = _make_free_user(db_session, limit=5, used=5)
    with pytest.raises(ValidationError) as exc_info:
        reserve_hosted_credit(db_session, user.id)
    assert exc_info.value.code == "hosted_credits.exhausted"
    db_session.rollback()
    db_session.refresh(user)
    assert user.hosted_credits_used == 5


def test_concurrent_reservations_single_winner(db_session: Session):
    """Two sessions race for the final credit; exactly one may succeed."""
    from database import engine

    user = _make_free_user(db_session, limit=5, used=4)

    session_a = Session(engine)
    session_b = Session(engine)
    try:
        # Both sessions load the user before either reserves (stale reads),
        # reproducing the interleaving that used to double-spend a credit.
        user_a = session_a.get(User, user.id)
        user_b = session_b.get(User, user.id)
        assert user_a.hosted_credits_used == 4
        assert user_b.hosted_credits_used == 4

        reserve_hosted_credit(session_a, user.id)
        session_a.commit()

        # Session B still holds a stale ORM snapshot (used == 4), but the
        # atomic guard is evaluated by the database and must reject it.
        with pytest.raises(ValidationError) as exc_info:
            reserve_hosted_credit(session_b, user.id)
        assert exc_info.value.code == "hosted_credits.exhausted"
        session_b.rollback()

        db_session.refresh(user)
        assert user.hosted_credits_used == 5
    finally:
        session_a.close()
        session_b.close()


def test_refund_decrements_and_floors_at_zero(db_session: Session):
    user = _make_free_user(db_session, limit=5, used=1)
    refund_hosted_credit(db_session, user.id)
    db_session.commit()
    db_session.refresh(user)
    assert user.hosted_credits_used == 0


def test_exact_reservation_is_bound_to_user_kind_and_debate(db_session: Session):
    owner = _make_free_user(db_session, limit=5, used=0)
    other = _make_free_user(db_session, limit=5, used=0)
    reservation_id = reserve_hosted_credit(
        db_session, owner.id, debate_id="debate-owned", run_attempt=1
    )
    assert reservation_id

    assert (
        refund_hosted_credit(
            db_session,
            other.id,
            reservation_id=reservation_id,
            debate_id="debate-owned",
        )
        is False
    )
    assert (
        consume_hosted_credit(
            db_session,
            owner.id,
            reservation_id=reservation_id,
            debate_id="debate-wrong",
        )
        is False
    )
    assert refund_hosted_credit(db_session, owner.id, reservation_id=reservation_id) is False


def test_reserved_credit_refunds_even_if_plan_changes(db_session: Session, monkeypatch):
    user = _make_free_user(db_session, limit=5, used=0)
    reservation_id = reserve_hosted_credit(
        db_session, user.id, debate_id="debate-upgraded", run_attempt=1
    )
    db_session.commit()

    # Refund is governed by the durable reservation, never today's plan.
    monkeypatch.setattr(
        "billing.service.get_active_plan",
        lambda *_args, **_kwargs: pytest.fail("refund must not re-check the plan"),
    )
    assert (
        refund_hosted_credit(
            db_session,
            user.id,
            reservation_id=reservation_id,
            debate_id="debate-upgraded",
        )
        is True
    )
    db_session.commit()
    db_session.refresh(user)
    assert user.hosted_credits_used == 0
    # A second refund must not drive the counter negative.
    refund_hosted_credit(db_session, user.id)
    db_session.commit()
    db_session.refresh(user)
    assert user.hosted_credits_used == 0
