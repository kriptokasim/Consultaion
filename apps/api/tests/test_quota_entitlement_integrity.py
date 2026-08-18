from datetime import timedelta

import pytest
from billing.models import BillingPlan, BillingSubscription
from billing.service import get_or_create_usage, increment_debate_usage
from config import settings
from exceptions import RateLimitError as AppRateLimitError
from models import UsageCounter, User, utcnow
from sqlmodel import Session, select
from usage_limits import (
    QuotaExceededError,
    RateLimitError as UsageRateLimitError,
    check_quota,
    increment_export_usage_daily,
    reserve_run_slot,
)


def _user(session: Session, email: str, *, marker_plan: str) -> User:
    user = User(
        email=email,
        password_hash="hashed",
        plan=marker_plan,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _plan(session: Session, slug: str) -> BillingPlan:
    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == slug)).first()
    assert plan is not None
    return plan


def _activate_pro(session: Session, user: User) -> BillingSubscription:
    now = utcnow()
    pro = _plan(session, "pro")
    sub = BillingSubscription(
        user_id=user.id,
        plan_id=pro.id,
        status="active",
        provider="stripe",
        provider_subscription_id=f"sub-{user.id}",
        current_period_start=now - timedelta(minutes=1),
        current_period_end=now + timedelta(days=30),
    )
    session.add(sub)
    session.commit()
    return sub


def test_usage_rate_limit_is_canonical_app_error():
    assert issubclass(UsageRateLimitError, AppRateLimitError)
    error = AppRateLimitError(
        message="Billing limit exceeded",
        code="billing.limit",
        details={"reset_at": "2030-01-01T00:00:00+00:00"},
    )
    assert error.detail == "Billing limit exceeded"
    assert error.reset_at == "2030-01-01T00:00:00+00:00"


def test_legacy_pro_marker_does_not_grant_paid_daily_quota(db_session: Session):
    user = _user(db_session, "marker-only-pro@example.com", marker_plan="pro")

    with pytest.raises(QuotaExceededError) as exc:
        check_quota(db_session, user, required_tokens=200_000)

    assert exc.value.kind == "tokens"
    assert exc.value.limit == 100_000


def test_active_subscription_grants_paid_daily_quota_even_with_free_marker(db_session: Session):
    user = _user(db_session, "canonical-pro@example.com", marker_plan="free")
    _activate_pro(db_session, user)

    # 200k is above the static Free daily policy (100k) but below Pro (1m).
    check_quota(db_session, user, required_tokens=200_000)


def test_run_slot_token_headroom_uses_canonical_plan(db_session: Session):
    marker_only = _user(db_session, "slot-marker@example.com", marker_plan="pro")
    db_session.add(
        UsageCounter(
            user_id=marker_only.id,
            period="day",
            tokens_used=120_000,
            window_start=utcnow(),
        )
    )
    db_session.commit()
    with pytest.raises(AppRateLimitError):
        reserve_run_slot(db_session, marker_only.id)

    canonical_pro = _user(db_session, "slot-paid@example.com", marker_plan="free")
    _activate_pro(db_session, canonical_pro)
    db_session.add(
        UsageCounter(
            user_id=canonical_pro.id,
            period="day",
            tokens_used=200_000,
            window_start=utcnow(),
        )
    )
    db_session.commit()

    # The legacy global UsageQuota default is 150k, so this would have blocked
    # a paid user before run-slot headroom was aligned to canonical entitlement.
    reserve_run_slot(db_session, canonical_pro.id)


def test_daily_export_increment_uses_canonical_entitlement(db_session: Session):
    marker_only = _user(db_session, "marker-export@example.com", marker_plan="pro")
    db_session.add(
        UsageCounter(
            user_id=marker_only.id,
            period="day",
            exports_used=5,
            window_start=utcnow(),
        )
    )
    db_session.commit()

    with pytest.raises(AppRateLimitError) as exc:
        increment_export_usage_daily(db_session, marker_only.id)
    assert exc.value.code == "quota.exports_exceeded"

    canonical_pro = _user(db_session, "paid-export@example.com", marker_plan="free")
    _activate_pro(db_session, canonical_pro)
    db_session.add(
        UsageCounter(
            user_id=canonical_pro.id,
            period="day",
            exports_used=5,
            window_start=utcnow(),
        )
    )
    db_session.commit()

    increment_export_usage_daily(db_session, canonical_pro.id)
    db_session.commit()
    counter = db_session.exec(
        select(UsageCounter).where(
            UsageCounter.user_id == canonical_pro.id,
            UsageCounter.period == "day",
        )
    ).first()
    assert counter is not None
    assert counter.exports_used == 6


def test_rejected_monthly_run_does_not_leak_into_usage(db_session: Session, monkeypatch):
    monkeypatch.setattr(settings, "ENV", "production")
    user = _user(db_session, "monthly-limit@example.com", marker_plan="free")
    free = _plan(db_session, "free")
    free.limits = {**(free.limits or {}), "max_debates_per_month": 1}
    db_session.add(free)

    usage = get_or_create_usage(db_session, user.id)
    usage.debates_created = 1
    db_session.add(usage)
    db_session.commit()

    with pytest.raises(AppRateLimitError):
        increment_debate_usage(db_session, user.id)

    # Simulate the caller committing some independent refund bookkeeping after
    # the rejection. The rejected monthly increment must still remain reverted.
    db_session.commit()
    db_session.expire_all()
    persisted = get_or_create_usage(db_session, user.id)
    assert persisted.debates_created == 1
