from datetime import timedelta

import pytest
from billing.models import BillingPlan, BillingSubscription
from models import User, utcnow
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select


def test_provider_subscription_identity_is_unique(db_session: Session):
    user = User(
        email="subscription-unique@example.com",
        password_hash="hashed",
        plan="free",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    pro = db_session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    assert pro is not None
    now = utcnow()
    provider_ref = "sub-shared-provider-ref"

    db_session.add(
        BillingSubscription(
            user_id=user.id,
            plan_id=pro.id,
            status="active",
            provider="stripe",
            provider_subscription_id=provider_ref,
            current_period_start=now - timedelta(minutes=1),
            current_period_end=now + timedelta(days=30),
        )
    )
    db_session.commit()

    db_session.add(
        BillingSubscription(
            user_id=user.id,
            plan_id=pro.id,
            status="pending",
            provider="stripe",
            provider_subscription_id=provider_ref,
            current_period_start=now,
            current_period_end=now,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
