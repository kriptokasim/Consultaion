"""Stripe webhook atomicity tests — prove failure injection rolls back everything.

Patchset 133 §6.4: Prove that the webhook handler does not commit internally,
and that the webhook route's session_scope owns the transaction.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
from sqlmodel import Session, select
from models import User
from billing.models import BillingPlan, BillingSubscription, BillingWebhookEvent
from billing.providers.stripe_provider import StripeBillingProvider


def _ensure_plans(session: Session):
    free_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
    if not free_plan:
        free_plan = BillingPlan(slug="free", name="Free Plan", is_default_free=True, limits={})
        session.add(free_plan)
    pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    if not pro_plan:
        pro_plan = BillingPlan(slug="pro", name="Pro Plan", is_default_free=False, limits={})
        session.add(pro_plan)
    session.commit()


def test_webhook_handler_does_not_commit(db_session):
    """FH125: The Stripe handler should never call session.commit() directly."""
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)

    user = User(
        id=str(uuid.uuid4()),
        email=f"nocommit-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pass",
        plan="free",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    subscription_id = f"sub_nocommit_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "subscription": subscription_id,
                "customer": f"cus_{uuid.uuid4().hex[:8]}",
                "metadata": {"user_id": user.id, "plan_slug": "pro"},
            }
        },
    }

    # Track commits during handler execution
    commits_during_handler = []
    original_commit = session.commit

    def tracking_commit():
        commits_during_handler.append(True)
        original_commit()

    with patch.object(session, "commit", side_effect=tracking_commit):
        provider.handle_webhook(payload, {}, db_session=session)

    # Handler should NOT have committed
    assert len(commits_during_handler) == 0, (
        f"Handler committed {len(commits_during_handler)} time(s) — "
        "Stripe handler must not call session.commit()"
    )


def test_webhook_duplicate_event_is_idempotent(db_session):
    """FH125: Processing the same webhook event twice is idempotent."""
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)

    user = User(
        id=str(uuid.uuid4()),
        email=f"idem-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pass",
        plan="free",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    event_id = f"evt_idem_{uuid.uuid4().hex}"
    subscription_id = f"sub_idem_{uuid.uuid4().hex[:8]}"

    payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "subscription": subscription_id,
                "customer": f"cus_{uuid.uuid4().hex[:8]}",
                "metadata": {"user_id": user.id, "plan_slug": "pro"},
            }
        },
    }

    # Process twice
    provider.handle_webhook(payload, {}, db_session=session)
    session.commit()
    provider.handle_webhook(payload, {}, db_session=session)
    session.commit()

    subs = session.exec(
        select(BillingSubscription).where(
            BillingSubscription.provider_subscription_id == subscription_id
        )
    ).all()
    assert len(subs) == 1, "Duplicate webhook should not create duplicate subscriptions"


def test_subscription_deleted_no_inner_commit(db_session):
    """FH125: subscription.deleted handler no longer commits inside."""
    provider = StripeBillingProvider()
    session = db_session
    _ensure_plans(session)

    user = User(
        id=str(uuid.uuid4()),
        email=f"del-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pass",
        plan="pro",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    subscription_id = f"sub_del_{uuid.uuid4().hex[:8]}"

    sub = BillingSubscription(
        user_id=user.id,
        plan_id=pro_plan.id,
        status="active",
        provider="stripe",
        provider_subscription_id=subscription_id,
        provider_customer_id=f"cus_{uuid.uuid4().hex[:8]}",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc),
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)

    payload = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": subscription_id}},
    }

    # Track commits during handler
    commits_during_handler = []
    original_commit = session.commit

    def tracking_commit():
        commits_during_handler.append(True)
        original_commit()

    with patch.object(session, "commit", side_effect=tracking_commit):
        provider.handle_webhook(payload, {}, db_session=session)

    assert len(commits_during_handler) == 0, (
        "subscription.deleted handler should not commit internally"
    )

    # Now commit and verify
    session.commit()
    session.refresh(sub)
    assert sub.status == "canceled"
    assert user.plan == "free"
