from datetime import timedelta

from billing.models import BillingPlan, BillingSubscription
from models import User, utcnow
from plan_config import resolve_plan_for_user
from routes.common import serialize_user
from sqlmodel import Session, select


def _plan(session: Session, slug: str) -> BillingPlan:
    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == slug)).first()
    assert plan is not None
    return plan


def test_attached_user_serialization_uses_canonical_entitlement(db_session: Session):
    # Stale legacy marker must not make a user-facing response look paid.
    user = User(
        email="serialize-plan@example.com",
        password_hash="hashed",
        plan="pro",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert resolve_plan_for_user(user) == "free"
    assert serialize_user(user)["plan"] == "free"

    pro = _plan(db_session, "pro")
    now = utcnow()
    subscription = BillingSubscription(
        user_id=user.id,
        plan_id=pro.id,
        status="active",
        provider="stripe",
        provider_subscription_id="sub-serialize-plan",
        current_period_start=now - timedelta(minutes=1),
        current_period_end=now + timedelta(days=30),
    )
    db_session.add(subscription)
    db_session.commit()

    assert resolve_plan_for_user(user) == "pro"
    assert serialize_user(user)["plan"] == "pro"

    # Once the canonical period expires, the API display immediately returns
    # Free even if maintenance has not yet repaired the compatibility marker.
    subscription.current_period_end = utcnow() - timedelta(seconds=1)
    user.plan = "pro"
    db_session.add(subscription)
    db_session.add(user)
    db_session.commit()

    assert resolve_plan_for_user(user) == "free"
    assert serialize_user(user)["plan"] == "free"


def test_detached_user_serialization_keeps_compatibility_fallback(db_session: Session):
    user = User(
        email="serialize-detached@example.com",
        password_hash="hashed",
        plan="pro",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.expunge(user)

    assert resolve_plan_for_user(user) == "pro"
