from datetime import timedelta

import pytest
from billing.manual_entitlements import (
    MANUAL_PROVIDER,
    MANUAL_SOURCE,
    grant_manual_entitlement,
    revoke_manual_entitlements,
)
from billing.models import BillingPlan, BillingSubscription
from billing.service import get_active_plan
from exceptions import ValidationError
from models import User, utcnow
from sqlmodel import Session, select


def _plan(session: Session, slug: str) -> BillingPlan:
    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == slug)).first()
    assert plan is not None
    return plan


def _user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="hashed", plan="free", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_manual_grant_is_entitled_but_not_paid_active_revenue(db_session: Session):
    user = _user(db_session, "manual-grant@example.com")
    admin = _user(db_session, "manual-admin@example.com")

    grant = grant_manual_entitlement(
        db_session,
        user_id=user.id,
        plan_slug="pro",
        granted_by_user_id=admin.id,
        reason="Seven-day design-partner evaluation",
        expires_at=utcnow() + timedelta(days=7),
    )
    db_session.commit()
    db_session.refresh(grant)
    db_session.refresh(user)

    assert grant.provider == MANUAL_PROVIDER
    assert grant.status == "trialing"
    assert grant.entitlement_source == MANUAL_SOURCE
    assert grant.entitlement_reason == "Seven-day design-partner evaluation"
    assert grant.granted_by_user_id == admin.id
    assert user.plan == "pro"
    assert get_active_plan(db_session, user.id).slug == "pro"

    # Investor MRR/paid-conversion queries intentionally count only `active`
    # subscriptions; a manual support/trial grant must not become paid revenue.
    paid_active = db_session.exec(
        select(BillingSubscription)
        .where(BillingSubscription.user_id == user.id)
        .where(BillingSubscription.status == "active")
    ).all()
    assert paid_active == []


def test_manual_grant_replaces_previous_manual_grant(db_session: Session):
    user = _user(db_session, "manual-replace@example.com")
    admin = _user(db_session, "manual-replace-admin@example.com")

    first = grant_manual_entitlement(
        db_session,
        user_id=user.id,
        plan_slug="pro",
        granted_by_user_id=admin.id,
        reason="First grant",
        expires_at=utcnow() + timedelta(days=5),
    )
    db_session.commit()

    second = grant_manual_entitlement(
        db_session,
        user_id=user.id,
        plan_slug="pro",
        granted_by_user_id=admin.id,
        reason="Replacement grant",
        expires_at=utcnow() + timedelta(days=10),
    )
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.status == "canceled"
    assert second.status == "trialing"
    assert get_active_plan(db_session, user.id).slug == "pro"


def test_manual_entitlement_revoke_returns_to_canonical_free(db_session: Session):
    user = _user(db_session, "manual-revoke@example.com")
    admin = _user(db_session, "manual-revoke-admin@example.com")

    grant_manual_entitlement(
        db_session,
        user_id=user.id,
        plan_slug="pro",
        granted_by_user_id=admin.id,
        reason="Temporary grant",
        expires_at=utcnow() + timedelta(days=3),
    )
    db_session.commit()

    assert revoke_manual_entitlements(db_session, user_id=user.id) == 1
    db_session.commit()
    db_session.refresh(user)

    assert get_active_plan(db_session, user.id).slug == "free"
    assert user.plan == "free"


def test_manual_grant_does_not_override_provider_backed_subscription(db_session: Session):
    user = _user(db_session, "paid-user@example.com")
    admin = _user(db_session, "paid-admin@example.com")
    pro = _plan(db_session, "pro")
    now = utcnow()
    db_session.add(
        BillingSubscription(
            user_id=user.id,
            plan_id=pro.id,
            status="active",
            provider="stripe",
            provider_subscription_id="sub-paid-user",
            current_period_start=now - timedelta(minutes=1),
            current_period_end=now + timedelta(days=30),
        )
    )
    db_session.commit()

    with pytest.raises(ValidationError) as exc:
        grant_manual_entitlement(
            db_session,
            user_id=user.id,
            plan_slug="pro",
            granted_by_user_id=admin.id,
            reason="Should not shadow paid state",
            expires_at=now + timedelta(days=7),
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "billing.manual_conflicts_with_provider_subscription"


def test_manual_grant_must_be_time_bounded(db_session: Session):
    user = _user(db_session, "manual-expiry@example.com")
    admin = _user(db_session, "manual-expiry-admin@example.com")

    with pytest.raises(ValidationError) as exc:
        grant_manual_entitlement(
            db_session,
            user_id=user.id,
            plan_slug="pro",
            granted_by_user_id=admin.id,
            reason="Too long",
            expires_at=utcnow() + timedelta(days=31),
        )

    assert exc.value.code == "billing.manual_expiry_too_far"
