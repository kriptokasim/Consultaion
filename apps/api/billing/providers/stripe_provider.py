from __future__ import annotations

import logging
from typing import Dict
from uuid import UUID

try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover
    stripe = None

from config import settings
from integrations.events import emit_event

from billing.models import BillingPlan

from .base import BillingProvider

logger = logging.getLogger(__name__)


class StripeBillingProvider(BillingProvider):
    def __init__(self):
        self.secret_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        self.success_url = settings.BILLING_CHECKOUT_SUCCESS_URL or settings.WEB_APP_ORIGIN or ""
        self.cancel_url = settings.BILLING_CHECKOUT_CANCEL_URL or settings.WEB_APP_ORIGIN or ""
        self.plan_price_map: Dict[str, str] = {
            "pro": settings.STRIPE_PRICE_PRO_ID or "",
        }

    def create_checkout_session(self, user_id: UUID, plan: BillingPlan) -> str:
        if not self.secret_key or not stripe:
            raise RuntimeError(
                "Stripe billing is not configured. Set STRIPE_SECRET_KEY and install stripe SDK."
            )

        price_id = self.plan_price_map.get(plan.slug)
        if not price_id:
            raise RuntimeError(
                f"No Stripe price ID configured for plan '{plan.slug}'. Set STRIPE_PRICE_PRO_ID."
            )

        stripe.api_key = self.secret_key
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer_email=None,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=self.success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=self.cancel_url,
                metadata={"user_id": str(user_id), "plan_slug": plan.slug},
            )
            return session.url  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - external dependency
            logger.exception("Stripe checkout session creation failed: %s", exc)
            raise

    def handle_webhook(self, payload: Dict, headers: Dict, db_session = None) -> None:
        from datetime import datetime, timezone
        from sqlmodel import select
        from models import User
        from billing.models import BillingPlan, BillingSubscription

        event_type = payload.get("type")
        logger.info("Received Stripe webhook event=%s", event_type)
        data = (payload.get("data") or {}).get("object") or {}
        
        # Idempotency / Duplicate Check
        event_id = payload.get("id")
        if event_id and db_session:
            from billing.models import BillingWebhookEvent
            existing = db_session.get(BillingWebhookEvent, event_id)
            if existing:
                logger.info("Stripe webhook event=%s already processed, ignoring", event_id)
                return
            
            # Record the event in session (will be committed with the transaction)
            evt = BillingWebhookEvent(id=event_id, provider="stripe", event_type=event_type)
            db_session.add(evt)


        if event_type == "checkout.session.completed" and db_session:
            metadata = data.get("metadata") or {}
            user_id = metadata.get("user_id")
            plan_slug = metadata.get("plan_slug")
            subscription_id = data.get("subscription")
            customer_id = data.get("customer")

            if user_id and plan_slug:
                plan_ref = db_session.exec(select(BillingPlan).where(BillingPlan.slug == plan_slug)).first()
                if not plan_ref:
                    logger.error("Plan not found during webhook: slug=%s", plan_slug)
                    return

                # Update user subscription plan
                user = db_session.get(User, user_id)
                if user:
                    user.plan = plan_slug
                    db_session.add(user)

                # Upsert BillingSubscription
                sub = db_session.exec(
                    select(BillingSubscription).where(
                        BillingSubscription.provider_subscription_id == subscription_id
                    )
                ).first()

                now = datetime.now(timezone.utc)
                if not sub:
                    sub = BillingSubscription(
                        user_id=user_id,
                        plan_id=plan_ref.id,
                        status="active",
                        provider="stripe",
                        provider_subscription_id=subscription_id,
                        provider_customer_id=customer_id,
                        current_period_start=now,
                        current_period_end=now,  # will be updated by customer.subscription.updated
                    )
                else:
                    sub.status = "active"
                    sub.plan_id = plan_ref.id

                db_session.add(sub)
                # Don't commit here — let the webhook route transaction own the commit
                # Side effects emitted after outer commit in webhook route

        elif event_type in ("customer.subscription.created", "customer.subscription.updated") and db_session:
            subscription_id = data.get("id")
            customer_id = data.get("customer")
            status = data.get("status")
            cancel_at_period_end = data.get("cancel_at_period_end", False)
            metadata = data.get("metadata") or {}
            user_id = metadata.get("user_id")
            plan_slug = metadata.get("plan_slug")

            # Resolve user_id/plan_slug if missing from subscription metadata
            sub = db_session.exec(
                select(BillingSubscription).where(
                    BillingSubscription.provider_subscription_id == subscription_id
                )
            ).first()

            if sub:
                user_id = user_id or sub.user_id
                if not plan_slug:
                    plan_ref = db_session.get(BillingPlan, sub.plan_id)
                    plan_slug = plan_ref.slug if plan_ref else None
            elif user_id and plan_slug:
                plan_ref = db_session.exec(select(BillingPlan).where(BillingPlan.slug == plan_slug)).first()
                if plan_ref:
                    sub = BillingSubscription(
                        user_id=user_id,
                        plan_id=plan_ref.id,
                        status=status,
                        provider="stripe",
                        provider_subscription_id=subscription_id,
                        provider_customer_id=customer_id,
                        current_period_start=datetime.now(timezone.utc),
                        current_period_end=datetime.now(timezone.utc),
                    )

            if sub:
                sub.status = status
                sub.cancel_at_period_end = bool(cancel_at_period_end)
                
                start_ts = data.get("current_period_start")
                if start_ts:
                    sub.current_period_start = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                
                end_ts = data.get("current_period_end")
                if end_ts:
                    sub.current_period_end = datetime.fromtimestamp(end_ts, tz=timezone.utc)

                db_session.add(sub)

                # Update User
                user = db_session.get(User, user_id)
                if user:
                    user.plan = plan_slug if status in ("active", "trialing") else "free"
                    db_session.add(user)
                # Don't commit here — let the webhook route transaction own the commit

        elif event_type == "customer.subscription.deleted" and db_session:
            subscription_id = data.get("id")
            sub = db_session.exec(
                select(BillingSubscription).where(
                    BillingSubscription.provider_subscription_id == subscription_id
                )
            ).first()

            if sub:
                sub.status = "canceled"
                sub.updated_at = datetime.now(timezone.utc)
                db_session.add(sub)

                # Reset user plan to free
                user = db_session.get(User, sub.user_id)
                if user:
                    user.plan = "free"
                    db_session.add(user)

                # Don't commit here — let the webhook route transaction own the commit
                # Side effects emitted after outer commit in webhook route
