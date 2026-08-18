import uuid
from datetime import datetime, timedelta, timezone

from billing.models import BillingPlan, BillingSubscription, BillingWebhookEvent
from billing.providers.stripe_provider import StripeBillingProvider
from models import User
from sqlmodel import Session, select


def _ensure_plans(session: Session):
    free_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "free")).first()
    if not free_plan:
        session.add(BillingPlan(slug="free", name="Free", is_default_free=True, limits={}))
    pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    if not pro_plan:
        session.add(BillingPlan(slug="pro", name="Pro", is_default_free=False, limits={}))
    session.commit()


def _make_user(session: Session, *, plan: str = "pro") -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"stripe-order-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        plan=plan,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_older_active_update_cannot_reactivate_newer_deletion(db_session: Session):
    provider = StripeBillingProvider()
    _ensure_plans(db_session)
    user = _make_user(db_session)
    pro = db_session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    now = datetime.now(timezone.utc)
    base = int(now.timestamp())
    sub_id = f"sub_fenced_{uuid.uuid4().hex[:10]}"

    sub = BillingSubscription(
        user_id=user.id,
        plan_id=pro.id,
        status="active",
        provider="stripe",
        provider_subscription_id=sub_id,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=30),
        provider_event_created_at=datetime.fromtimestamp(base, tz=timezone.utc),
    )
    db_session.add(sub)
    db_session.commit()

    deleted_event_id = f"evt_delete_{uuid.uuid4().hex}"
    deleted = {
        "id": deleted_event_id,
        "created": base + 20,
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": sub_id}},
    }
    provider.handle_webhook(deleted, {}, db_session=db_session)
    db_session.commit()
    db_session.refresh(sub)
    db_session.refresh(user)
    assert sub.status == "canceled"
    assert sub.provider_event_created_at == datetime.fromtimestamp(base + 20, tz=timezone.utc)
    assert user.plan == "free"

    stale_event_id = f"evt_stale_{uuid.uuid4().hex}"
    stale_active = {
        "id": stale_event_id,
        "created": base + 10,
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": sub_id,
            "status": "active",
            "current_period_start": int((now - timedelta(days=1)).timestamp()),
            "current_period_end": int((now + timedelta(days=30)).timestamp()),
        }},
    }
    provider.handle_webhook(stale_active, {}, db_session=db_session)
    db_session.commit()
    db_session.refresh(sub)
    db_session.refresh(user)

    assert stale_active["_consultaion_stale"] is True
    assert sub.status == "canceled"
    assert sub.provider_event_created_at == datetime.fromtimestamp(base + 20, tz=timezone.utc)
    assert user.plan == "free"
    assert db_session.get(BillingWebhookEvent, stale_event_id) is not None


def test_deletion_before_local_association_creates_tombstone_and_fences_older_activation(
    db_session: Session,
):
    provider = StripeBillingProvider()
    _ensure_plans(db_session)
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    base = int(now.timestamp())
    sub_id = f"sub_tombstone_{uuid.uuid4().hex[:10]}"

    deleted = {
        "id": f"evt_tomb_delete_{uuid.uuid4().hex}",
        "created": base + 20,
        "type": "customer.subscription.deleted",
        "data": {"object": {
            "id": sub_id,
            "customer": "cus_tombstone",
            "metadata": {"user_id": user.id, "plan_slug": "pro"},
            "current_period_start": int((now - timedelta(days=1)).timestamp()),
            "current_period_end": int((now + timedelta(days=30)).timestamp()),
        }},
    }
    provider.handle_webhook(deleted, {}, db_session=db_session)
    db_session.commit()

    tombstone = db_session.exec(
        select(BillingSubscription).where(BillingSubscription.provider_subscription_id == sub_id)
    ).first()
    assert tombstone is not None
    assert tombstone.status == "canceled"
    assert tombstone.provider_event_created_at == datetime.fromtimestamp(base + 20, tz=timezone.utc)

    older_created = {
        "id": f"evt_old_create_{uuid.uuid4().hex}",
        "created": base + 10,
        "type": "customer.subscription.created",
        "data": {"object": {
            "id": sub_id,
            "customer": "cus_tombstone",
            "status": "active",
            "metadata": {"user_id": user.id, "plan_slug": "pro"},
            "current_period_start": int((now - timedelta(days=1)).timestamp()),
            "current_period_end": int((now + timedelta(days=30)).timestamp()),
        }},
    }
    provider.handle_webhook(older_created, {}, db_session=db_session)
    db_session.commit()
    db_session.refresh(tombstone)
    db_session.refresh(user)

    assert older_created["_consultaion_stale"] is True
    assert tombstone.status == "canceled"
    assert user.plan == "free"


def test_duplicate_delivery_marks_payload_for_side_effect_dedupe(db_session: Session):
    provider = StripeBillingProvider()
    _ensure_plans(db_session)
    user = _make_user(db_session, plan="free")
    sub_id = f"sub_duplicate_{uuid.uuid4().hex[:10]}"
    event_id = f"evt_duplicate_{uuid.uuid4().hex}"
    payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {"object": {
            "subscription": sub_id,
            "customer": "cus_duplicate",
            "metadata": {"user_id": user.id, "plan_slug": "pro"},
        }},
    }

    provider.handle_webhook(payload, {}, db_session=db_session)
    db_session.commit()

    duplicate_payload = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": payload["data"],
    }
    provider.handle_webhook(duplicate_payload, {}, db_session=db_session)
    assert duplicate_payload["_consultaion_duplicate"] is True
