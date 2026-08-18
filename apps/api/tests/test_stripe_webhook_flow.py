import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from billing.models import BillingPlan, BillingSubscription, BillingWebhookEvent
from billing.providers.stripe_provider import StripeBillingProvider
from models import User
from sqlmodel import Session, select


def _ensure_plans(session: Session):
    free_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
    if not free_plan:
        free_plan = BillingPlan(
            slug="free",
            name="Free Plan",
            is_default_free=True,
            limits={}
        )
        session.add(free_plan)

    pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    if not pro_plan:
        pro_plan = BillingPlan(
            slug="pro",
            name="Pro Plan",
            is_default_free=False,
            limits={}
        )
        session.add(pro_plan)
    session.commit()


def _make_user(session: Session, prefix: str, *, plan: str = "free") -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"{prefix}-{uuid.uuid4()}@example.com",
        password_hash="hashed_pass",
        plan=plan,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_checkout_session_copies_metadata_to_subscription(db_session):
    provider = StripeBillingProvider()
    _ensure_plans(db_session)
    pro_plan = db_session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()

    provider.secret_key = "sk_test"
    provider.plan_price_map["pro"] = "price_pro"
    fake_session = MagicMock(url="https://checkout.example/session")
    fake_stripe = MagicMock()
    fake_stripe.checkout.Session.create.return_value = fake_session

    with patch("billing.providers.stripe_provider.stripe", fake_stripe):
        url = provider.create_checkout_session(uuid.uuid4(), pro_plan)

    assert url == fake_session.url
    kwargs = fake_stripe.checkout.Session.create.call_args.kwargs
    assert kwargs["metadata"] == kwargs["subscription_data"]["metadata"]
    assert kwargs["metadata"]["plan_slug"] == "pro"
    assert kwargs["metadata"]["user_id"]


def test_stripe_webhook_checkout_completed_creates_pending_association(db_session):
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)
    user = _make_user(session, "webhook-test")

    subscription_id = f"sub_checkout_{uuid.uuid4().hex[:12]}"
    customer_id = f"cus_checkout_{uuid.uuid4().hex[:12]}"
    payload = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "subscription": subscription_id,
                "customer": customer_id,
                "metadata": {
                    "user_id": user.id,
                    "plan_slug": "pro",
                },
            }
        },
    }

    provider.handle_webhook(payload, {}, db_session=session)
    session.commit()
    session.refresh(user)

    assert user.plan == "free"
    sub = session.exec(
        select(BillingSubscription).where(
            BillingSubscription.provider_subscription_id == subscription_id
        )
    ).first()
    assert sub is not None
    assert sub.user_id == user.id
    assert sub.status == "pending"
    assert sub.provider == "stripe"
    assert sub.provider_customer_id == customer_id


def test_subscription_event_after_checkout_activates_entitlement(db_session):
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)
    user = _make_user(session, "ordered-webhook")
    subscription_id = f"sub_ordered_{uuid.uuid4().hex[:12]}"
    customer_id = f"cus_ordered_{uuid.uuid4().hex[:12]}"

    checkout = {
        "id": f"evt_checkout_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {"object": {
            "subscription": subscription_id,
            "customer": customer_id,
            "metadata": {"user_id": user.id, "plan_slug": "pro"},
        }},
    }
    provider.handle_webhook(checkout, {}, db_session=session)
    session.commit()

    now = datetime.now(timezone.utc)
    created = {
        "id": f"evt_sub_{uuid.uuid4().hex}",
        "type": "customer.subscription.created",
        "data": {"object": {
            "id": subscription_id,
            "customer": customer_id,
            "status": "active",
            # Deliberately omit metadata: existing checkout association must
            # be sufficient for older Stripe objects.
            "current_period_start": int((now - timedelta(minutes=1)).timestamp()),
            "current_period_end": int((now + timedelta(days=30)).timestamp()),
        }},
    }
    provider.handle_webhook(created, {}, db_session=session)
    session.commit()

    sub = session.exec(
        select(BillingSubscription).where(
            BillingSubscription.provider_subscription_id == subscription_id
        )
    ).first()
    session.refresh(user)
    assert sub.status == "active"
    assert sub.current_period_end > now
    assert user.plan == "pro"
    # Resolved DB context is propagated for post-commit integrations even when
    # the original Stripe subscription event had empty metadata.
    assert created["data"]["object"]["metadata"] == {
        "user_id": user.id,
        "plan_slug": "pro",
    }


def test_subscription_event_without_context_is_retryable(db_session):
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)
    event_id = f"evt_orphan_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    payload = {
        "id": event_id,
        "type": "customer.subscription.created",
        "data": {"object": {
            "id": f"sub_orphan_{uuid.uuid4().hex[:12]}",
            "customer": "cus_orphan",
            "status": "active",
            "metadata": {},
            "current_period_start": int(now.timestamp()),
            "current_period_end": int((now + timedelta(days=30)).timestamp()),
        }},
    }

    with pytest.raises(ValueError, match="Cannot resolve billing context"):
        provider.handle_webhook(payload, {}, db_session=session)

    assert session.get(BillingWebhookEvent, event_id) is None
    session.rollback()


def test_checkout_does_not_overwrite_trialing_status(db_session):
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)
    user = _make_user(session, "trial-order", plan="pro")
    pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    now = datetime.now(timezone.utc)
    subscription_id = f"sub_trial_{uuid.uuid4().hex[:12]}"
    sub = BillingSubscription(
        user_id=user.id,
        plan_id=pro_plan.id,
        status="trialing",
        provider="stripe",
        provider_subscription_id=subscription_id,
        provider_customer_id="cus_trial",
        current_period_start=now - timedelta(minutes=1),
        current_period_end=now + timedelta(days=14),
    )
    session.add(sub)
    session.commit()

    checkout = {
        "id": f"evt_checkout_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {"object": {
            "subscription": subscription_id,
            "customer": "cus_trial",
            "metadata": {"user_id": user.id, "plan_slug": "pro"},
        }},
    }
    provider.handle_webhook(checkout, {}, db_session=session)
    session.commit()
    session.refresh(sub)

    assert sub.status == "trialing"


def test_stripe_webhook_subscription_updated_and_deleted(db_session):
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)
    user = _make_user(session, "webhook-sub-test", plan="pro")
    pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()

    subscription_id = f"sub_update_{uuid.uuid4().hex[:12]}"
    customer_id = f"cus_update_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    sub = BillingSubscription(
        user_id=user.id,
        plan_id=pro_plan.id,
        status="active",
        provider="stripe",
        provider_subscription_id=subscription_id,
        provider_customer_id=customer_id,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)

    payload_update = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": subscription_id,
                "customer": customer_id,
                "status": "past_due",
                "cancel_at_period_end": True,
                "current_period_start": 1700000000,
                "current_period_end": 1703000000,
            }
        },
    }

    provider.handle_webhook(payload_update, {}, db_session=session)
    session.commit()
    session.refresh(sub)
    session.refresh(user)
    assert sub.status == "past_due"
    assert sub.cancel_at_period_end is True
    assert sub.current_period_start.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    assert sub.current_period_end.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(1703000000, tz=timezone.utc)
    assert user.plan == "free"

    payload_delete = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": subscription_id}},
    }
    provider.handle_webhook(payload_delete, {}, db_session=session)
    session.commit()
    session.refresh(sub)
    session.refresh(user)
    assert sub.status == "canceled"
    assert user.plan == "free"


def test_stripe_webhook_idempotency(db_session):
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)
    user = _make_user(session, "webhook-idem")

    subscription_id = f"sub_idem_{uuid.uuid4().hex[:12]}"
    customer_id = f"cus_idem_{uuid.uuid4().hex[:12]}"
    event_id = f"evt_{uuid.uuid4().hex}"
    payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "subscription": subscription_id,
                "customer": customer_id,
                "metadata": {"user_id": user.id, "plan_slug": "pro"},
            }
        },
    }

    provider.handle_webhook(payload, {}, db_session=session)
    session.commit()
    provider.handle_webhook(payload, {}, db_session=session)

    subs = session.exec(
        select(BillingSubscription).where(
            BillingSubscription.provider_subscription_id == subscription_id
        )
    ).all()
    assert len(subs) == 1
    assert session.get(BillingWebhookEvent, event_id) is not None
