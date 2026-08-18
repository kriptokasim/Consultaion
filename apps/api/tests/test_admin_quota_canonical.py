from datetime import timedelta

from billing.models import BillingPlan, BillingSubscription
from models import User, utcnow
from plan_config import get_plan_limits
from routes.admin.usage import admin_quota_usage, admin_usage_overview
from sqlmodel import Session, select


def _plan(session: Session, slug: str) -> BillingPlan:
    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == slug)).first()
    assert plan is not None
    return plan


def _user(session: Session, email: str, marker: str) -> User:
    user = User(email=email, password_hash="hashed", plan=marker, is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_admin_quota_filters_and_limits_use_canonical_entitlement(db_session: Session):
    admin = _user(db_session, "quota-admin@example.com", "free")
    stale_marker = _user(db_session, "quota-stale@example.com", "pro")
    entitled = _user(db_session, "quota-entitled@example.com", "free")
    pro = _plan(db_session, "pro")
    now = utcnow()

    db_session.add(
        BillingSubscription(
            user_id=entitled.id,
            plan_id=pro.id,
            status="trialing",
            provider="manual",
            provider_subscription_id="manual:quota-entitled",
            current_period_start=now - timedelta(minutes=1),
            current_period_end=now + timedelta(days=7),
        )
    )
    db_session.commit()

    payload = admin_quota_usage(
        email=None,
        plan="pro",
        limit=50,
        session=db_session,
        _=admin,
    )

    assert [row["user_id"] for row in payload["users"]] == [entitled.id]
    row = payload["users"][0]
    assert row["plan"] == "pro"

    static = get_plan_limits("pro")
    configured_token = (pro.limits or {}).get("max_tokens_per_day")
    expected_token = int(configured_token) if configured_token is not None else static.daily_token_limit
    configured_export = (pro.limits or {}).get("max_exports_per_day")
    expected_export = int(configured_export) if configured_export is not None else static.daily_export_limit
    assert row["daily_token_limit"] == expected_token
    assert row["daily_export_limit"] == expected_export

    # A stale legacy Pro marker without entitlement must not pass the filter.
    assert stale_marker.id not in {item["user_id"] for item in payload["users"]}


def test_admin_usage_overview_includes_trialing_and_rejects_future_subscription(db_session: Session):
    admin = _user(db_session, "overview-admin@example.com", "free")
    trial_user = _user(db_session, "overview-trial@example.com", "free")
    future_user = _user(db_session, "overview-future@example.com", "pro")
    pro = _plan(db_session, "pro")
    now = utcnow()

    db_session.add_all(
        [
            BillingSubscription(
                user_id=trial_user.id,
                plan_id=pro.id,
                status="trialing",
                provider="manual",
                provider_subscription_id="manual:overview-trial",
                current_period_start=now - timedelta(minutes=1),
                current_period_end=now + timedelta(days=5),
            ),
            BillingSubscription(
                user_id=future_user.id,
                plan_id=pro.id,
                status="active",
                provider="stripe",
                provider_subscription_id="sub-overview-future",
                current_period_start=now + timedelta(days=1),
                current_period_end=now + timedelta(days=31),
            ),
        ]
    )
    db_session.commit()

    payload = admin_usage_overview(
        user_id=None,
        email=None,
        limit=100,
        offset=0,
        session=db_session,
        _=admin,
    )
    rows = {row["user_id"]: row for row in payload["items"]}

    assert rows[trial_user.id]["plan"]["slug"] == "pro"
    assert rows[future_user.id]["plan"]["slug"] == "free"
