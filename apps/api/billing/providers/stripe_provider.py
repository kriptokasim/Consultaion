from __future__ import annotations

import logging
import os
from typing import Dict
from uuid import UUID

try:
    import stripe  # type: ignore
except ImportError:  # pragma: no cover
    stripe = None

from billing.models import BillingPlan

from .base import BillingProvider

logger = logging.getLogger(__name__)


class StripeBillingProvider(BillingProvider):
    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        self.success_url = os.getenv("BILLING_CHECKOUT_SUCCESS_URL") or "https://example.com/success"
        self.cancel_url = os.getenv("BILLING_CHECKOUT_CANCEL_URL") or "https://example.com/canceled"
        self.plan_price_map: Dict[str, str] = {
            "pro": os.getenv("STRIPE_PRICE_PRO_ID", ""),
        }

    def create_checkout_session(self, user_id: UUID, plan: BillingPlan) -> str:
        if not self.secret_key or not stripe:
            logger.warning("Stripe secret key missing or stripe SDK unavailable; returning placeholder checkout URL.")
            return f"https://example.com/checkout/placeholder?plan={plan.slug}"

        price_id = self.plan_price_map.get(plan.slug)
        if not price_id:
            logger.warning("No Stripe price configured for plan %s; returning placeholder URL", plan.slug)
            return f"https://example.com/checkout/placeholder?plan={plan.slug}"

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

    def handle_webhook(self, payload: Dict, headers: Dict) -> None:
        event_type = payload.get("type")
        logger.info("Received Stripe webhook event=%s", event_type)
        # TODO: Validate signature with self.webhook_secret and update BillingSubscription entries.
        # For now we simply log the payload.
