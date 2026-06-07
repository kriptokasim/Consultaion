import pytest
import uuid
from datetime import datetime, timezone
from sqlmodel import Session, select
from database import engine
from models import User
from billing.models import BillingPlan, BillingSubscription
from billing.providers.stripe_provider import StripeBillingProvider

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

def test_stripe_webhook_checkout_completed():
    provider = StripeBillingProvider()
    
    with Session(engine) as session:
        _ensure_plans(session)
        # Create user
        unique_email = f"webhook-test-{uuid.uuid4()}@example.com"
        user = User(
            id=str(uuid.uuid4()),
            email=unique_email,
            password_hash="hashed_pass",
            plan="free",
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        user_id = user.id
        subscription_id = f"sub_checkout_{uuid.uuid4().hex[:12]}"
        customer_id = f"cus_checkout_{uuid.uuid4().hex[:12]}"
        
        # Build mock webhook payload for checkout.session.completed
        payload = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "subscription": subscription_id,
                    "customer": customer_id,
                    "metadata": {
                        "user_id": user_id,
                        "plan_slug": "pro"
                    }
                }
            }
        }
        
        # Process webhook
        provider.handle_webhook(payload, {}, db_session=session)
        
        # Assert user plan was upgraded to pro
        session.refresh(user)
        assert user.plan == "pro"
        
        # Assert BillingSubscription record was created
        sub = session.exec(
            select(BillingSubscription).where(
                BillingSubscription.provider_subscription_id == subscription_id
            )
        ).first()
        assert sub is not None
        assert sub.user_id == user_id
        assert sub.status == "active"
        assert sub.provider == "stripe"
        assert sub.provider_customer_id == customer_id

def test_stripe_webhook_subscription_updated_and_deleted():
    provider = StripeBillingProvider()
    
    with Session(engine) as session:
        _ensure_plans(session)
        
        unique_email = f"webhook-sub-test-{uuid.uuid4()}@example.com"
        user = User(
            id=str(uuid.uuid4()),
            email=unique_email,
            password_hash="hashed_pass",
            plan="pro",
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
        
        subscription_id = f"sub_update_{uuid.uuid4().hex[:12]}"
        customer_id = f"cus_update_{uuid.uuid4().hex[:12]}"

        # Pre-seed active subscription
        sub = BillingSubscription(
            user_id=user.id,
            plan_id=pro_plan.id,
            status="active",
            provider="stripe",
            provider_subscription_id=subscription_id,
            provider_customer_id=customer_id,
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc),
        )
        session.add(sub)
        session.commit()
        session.refresh(sub)
        
        # 1. Test subscription update event (status change to past_due)
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
            }
        }
        
        provider.handle_webhook(payload_update, {}, db_session=session)
        
        # Refresh and verify
        session.refresh(sub)
        session.refresh(user)
        assert sub.status == "past_due"
        assert sub.cancel_at_period_end is True
        assert sub.current_period_start.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(1700000000, tz=timezone.utc)
        assert sub.current_period_end.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(1703000000, tz=timezone.utc)
        # Plan becomes free if status not in active/trialing
        assert user.plan == "free"
        
        # 2. Test subscription deletion / cancellation event
        payload_delete = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": subscription_id
                }
            }
        }
        
        provider.handle_webhook(payload_delete, {}, db_session=session)
        
        session.refresh(sub)
        session.refresh(user)
        assert sub.status == "canceled"
        assert user.plan == "free"


def test_stripe_webhook_idempotency():
    """Verify that processing the same checkout.session.completed event twice is idempotent."""
    provider = StripeBillingProvider()
    
    with Session(engine) as session:
        _ensure_plans(session)
        unique_email = f"webhook-idem-{uuid.uuid4()}@example.com"
        user = User(
            id=str(uuid.uuid4()),
            email=unique_email,
            password_hash="hashed_pass",
            plan="free",
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        subscription_id = f"sub_idem_{uuid.uuid4().hex[:12]}"
        customer_id = f"cus_idem_{uuid.uuid4().hex[:12]}"
        
        payload = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "subscription": subscription_id,
                    "customer": customer_id,
                    "metadata": {
                        "user_id": user.id,
                        "plan_slug": "pro"
                    }
                }
            }
        }
        
        # Process once
        provider.handle_webhook(payload, {}, db_session=session)
        session.refresh(user)
        assert user.plan == "pro"
        
        # Process a second time (should be idempotent and not create duplicate or throw exception)
        provider.handle_webhook(payload, {}, db_session=session)
        
        session.refresh(user)
        assert user.plan == "pro"
        
        # Count subscriptions matching subscription_id
        subs = session.exec(
            select(BillingSubscription).where(
                BillingSubscription.provider_subscription_id == subscription_id
            )
        ).all()
        assert len(subs) == 1

