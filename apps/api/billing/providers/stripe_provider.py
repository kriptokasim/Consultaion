from __future__ import annotations

import logging
from typing import Dict

try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover
    stripe = None

from billing.models import BillingPlan
from config import settings

from .base import BillingProvider, BillingUserID

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

    def create_checkout_session(self, user_id: BillingUserID, plan: BillingPlan) -> str:
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
        metadata = {"user_id": str(user_id), "plan_slug": plan.slug}
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer_email=None,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=self.success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=self.cancel_url,
                metadata=metadata,
                subscription_data={"metadata": metadata},
            )
            return session.url  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - external dependency
            logger.exception("Stripe checkout session creation failed: %s", exc)
            raise

    def handle_webhook(self, payload: Dict, headers: Dict, db_session = None) -> None:
        from datetime import datetime, timezone

        from models import User
        from sqlmodel import select

        from billing.models import BillingPlan, BillingSubscription

        event_type = payload.get("type")
        logger.info("Received Stripe webhook event=%s", event_type)
        data = (payload.get("data") or {}).get("object") or {}

        event_id = payload.get("id")
        if event_id and db_session:
            from billing.models import BillingWebhookEvent
            existing = db_session.get(BillingWebhookEvent, event_id)
            if existing:
                logger.info("Stripe webhook event=%s already processed, ignoring", event_id)
                return

        if event_type == "checkout.session.completed" and db_session:
            metadata = data.get("metadata") or {}
            user_id = metadata.get("user_id")
            plan_slug = metadata.get("plan_slug")
            subscription_id = data.get("subscription")
            customer_id = data.get("customer")

            if not user_id or not plan_slug or not subscription_id:
                raise ValueError("checkout.session.completed is missing user_id, plan_slug, or subscription")

            plan_ref = db_session.exec(select(BillingPlan).where(BillingPlan.slug == plan_slug)).first()
            if not plan_ref:
                raise RuntimeError(f"Plan not found during webhook: slug={plan_slug}")

            user = db_session.get(User, user_id)
            if not user:
                raise RuntimeError(f"User not found during webhook: user_id={user_id}")

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
                    status="pending",
                    provider="stripe",
                    provider_subscription_id=subscription_id,
                    provider_customer_id=customer_id,
                    current_period_start=now,
                    current_period_end=now,
                )
            else:
                sub.plan_id = plan_ref.id
                sub.provider_customer_id = customer_id or sub.provider_customer_id

            db_session.add(sub)

        elif event_type in ("customer.subscription.created", "customer.subscription.updated") and db_session:
            subscription_id = data.get("id")
            customer_id = data.get("customer")
            status = data.get("status")
            cancel_at_period_end = data.get("cancel_at_period_end", False)
            metadata = data.get("metadata") or {}
            user_id = metadata.get("user_id")
            plan_slug = metadata.get("plan_slug")

            if not subscription_id or not status:
                raise ValueError(f"{event_type} is missing subscription id or status")

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
            else:
                if not user_id or not plan_slug:
                    raise ValueError(
                        f"Cannot resolve billing context for subscription {subscription_id}"
                    )
                plan_ref = db_session.exec(select(BillingPlan).where(BillingPlan.slug == plan_slug)).first()
                if not plan_ref:
                    raise RuntimeError(f"Plan not found during webhook: slug={plan_slug}")
                now = datetime.now(timezone.utc)
                sub = BillingSubscription(
                    user_id=user_id,
                    plan_id=plan_ref.id,
                    status=status,
                    provider="stripe",
                    provider_subscription_id=subscription_id,
                    provider_customer_id=customer_id,
                    current_period_start=now,
                    current_period_end=now,
                )

            if not user_id or not plan_slug:
                raise ValueError(
                    f"Resolved subscription {subscription_id} is missing user or plan context"
                )

            # Enrich the in-memory payload so post-commit side effects can use
            # the canonical DB-resolved context for legacy Stripe objects whose
            # subscription metadata was empty. This does not alter Stripe data.
            resolved_metadata = dict(metadata)
            resolved_metadata.setdefault("user_id", user_id)
            resolved_metadata.setdefault("plan_slug", plan_slug)
            data["metadata"] = resolved_metadata

            start_ts = data.get("current_period_start")
            end_ts = data.get("current_period_end")
            if status in ("active", "trialing") and (not start_ts or not end_ts):
                raise ValueError(
                    f"{event_type} missing current period for entitled status '{status}'"
                )

            sub.status = status
            sub.cancel_at_period_end = bool(cancel_at_period_end)
            sub.provider_customer_id = customer_id or sub.provider_customer_id

            if start_ts:
                sub.current_period_start = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            if end_ts:
                sub.current_period_end = datetime.fromtimestamp(end_ts, tz=timezone.utc)

            db_session.add(sub)

            user = db_session.get(User, user_id)
            if user:
                user.plan = plan_slug if status in ("active", "trialing") else "free"
                db_session.add(user)

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

                user = db_session.get(User, sub.user_id)
                if user:
                    user.plan = "free"
                    db_session.add(user)

        if event_id and db_session:
            from billing.models import BillingWebhookEvent
            db_session.add(
                BillingWebhookEvent(
                    id=event_id,
                    provider="stripe",
                    event_type=event_type or "unknown",
                )
            )
