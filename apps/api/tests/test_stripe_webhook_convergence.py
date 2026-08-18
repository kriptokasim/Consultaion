import uuid
from datetime import timedelta

from billing.models import BillingPlan, BillingSubscription
from billing.providers.stripe_provider import StripeBillingProvider
from models import User, utcnow
from sqlmodel import Session, select


def _user_and_pro(session: Session):
    user = User(
        email=f"stripe-convergence-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        plan="pro",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    pro = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    assert pro is not None
    return user, pro


def test_same_second_active_event_cannot_resurrect_canceled_subscription(db_session: Session):
    provider = StripeBillingProvider()
    user, pro = _user_and_pro(db_session)
    now = utcnow()
    created_second = int(now.timestamp())
    sub = BillingSubscription(
        user_id=user.id,
        plan_id=pro.id,
        status="canceled",
        provider="stripe",
        provider_subscription_id=f"sub-same-second-{uuid.uuid4().hex[:8]}",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=30),
        provider_event_created_at=now.replace(microsecond=0),
    )
    db_session.add(sub)
    db_session.commit()

    payload = {
        "id": f"evt-same-second-{uuid.uuid4().hex}",
        "created": created_second,
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": sub.provider_subscription_id,
            "status": "active",
            "metadata": {"user_id": user.id, "plan_slug": "pro"},
            "current_period_start": int((now - timedelta(days=1)).timestamp()),
            "current_period_end": int((now + timedelta(days=30)).timestamp()),
        }},
    }

    provider.handle_webhook(payload, {}, db_session=db_session)
    db_session.commit()
    db_session.refresh(sub)

    assert payload["_consultaion_stale"] is True
    assert sub.status == "canceled"


def test_non_entitled_event_does_not_drop_marker_when_other_subscription_is_active(
    db_session: Session,
):
    provider = StripeBillingProvider()
    user, pro = _user_and_pro(db_session)
    now = utcnow()

    changing = BillingSubscription(
        user_id=user.id,
        plan_id=pro.id,
        status="active",
        provider="stripe",
        provider_subscription_id=f"sub-changing-{uuid.uuid4().hex[:8]}",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=30),
        provider_event_created_at=now - timedelta(minutes=2),
    )
    remaining = BillingSubscription(
        user_id=user.id,
        plan_id=pro.id,
        status="active",
        provider="stripe",
        provider_subscription_id=f"sub-remaining-{uuid.uuid4().hex[:8]}",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=30),
        provider_event_created_at=now - timedelta(minutes=2),
    )
    db_session.add(changing)
    db_session.add(remaining)
    db_session.commit()

    payload = {
        "id": f"evt-past-due-{uuid.uuid4().hex}",
        "created": int(now.timestamp()),
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": changing.provider_subscription_id,
            "status": "past_due",
            "metadata": {"user_id": user.id, "plan_slug": "pro"},
        }},
    }
    provider.handle_webhook(payload, {}, db_session=db_session)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(changing)
    db_session.refresh(remaining)

    assert changing.status == "past_due"
    assert remaining.status == "active"
    assert user.plan == "pro"
