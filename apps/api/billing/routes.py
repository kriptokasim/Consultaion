from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select
from types import SimpleNamespace
import json

from auth import get_current_user
from config import settings
from deps import get_session
from model_registry import ALL_MODELS
from models import User

from .models import BillingPlan, BillingUsage
from .providers import get_billing_provider
from .service import (
    _current_period,
    get_active_plan,
    get_or_create_usage,
)

try:  # pragma: no cover - optional dependency guard
    import stripe as stripe_sdk  # type: ignore
except ImportError:  # pragma: no cover
    stripe_sdk = None


class _StripeWebhookStub:
    @staticmethod
    def construct_event(*_args, **_kwargs):
        raise RuntimeError("Stripe SDK unavailable")


stripe = stripe_sdk if stripe_sdk is not None else SimpleNamespace(Webhook=_StripeWebhookStub)

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)

MODEL_COST_PER_1K = {
    "router-smart": 0.50,
    "router-deep": 0.75,
    "gpt4o-mini": 0.60,
    "gpt4o-deep": 1.00,
    "claude-sonnet": 1.20,
    "claude-haiku": 0.35,
    "gemini-flash": 0.20,
    "gemini-pro": 0.90,
}


def _resolve_model_meta(model_id: str) -> Dict[str, object]:
    cfg = ALL_MODELS.get(model_id)
    return {
        "model_id": model_id,
        "display_name": cfg.display_name if cfg else model_id,
    }


@router.get("/usage/models")
def get_model_usage(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    period = _current_period()
    stmt = select(BillingUsage).where(BillingUsage.user_id == current_user.id, BillingUsage.period == period)
    usage = session.exec(stmt).first()
    if not usage or not usage.model_tokens:
        return {"items": []}

    items: List[Dict[str, object]] = []
    for model_id, tokens in usage.model_tokens.items():
        meta = _resolve_model_meta(model_id)
        cost_per_1k = MODEL_COST_PER_1K.get(model_id)
        approx_cost = None
        if cost_per_1k is not None:
            approx_cost = round((int(tokens) / 1000) * cost_per_1k, 4)
        items.append(
            {
                **meta,
                "tokens_used": int(tokens),
                "approx_cost_usd": approx_cost,
            }
        )
    return {"items": items}


@router.get("/plans")
def list_billing_plans(session: Session = Depends(get_session)):
    plans = session.exec(select(BillingPlan)).all()

    def sort_key(plan: BillingPlan):
        price = plan.price_monthly if plan.price_monthly is not None else float("inf")
        return (0 if plan.is_default_free else 1, float(price))

    plans.sort(key=sort_key)
    payload = [
        {
            "slug": plan.slug,
            "name": plan.name,
            "price_monthly": float(plan.price_monthly or 0.0) if plan.price_monthly is not None else None,
            "currency": plan.currency,
            "is_default_free": plan.is_default_free,
            "limits": plan.limits or {},
        }
        for plan in plans
    ]
    return {"items": payload}


class CheckoutRequest(BaseModel):
    plan_slug: str


@router.get("/me")
def get_billing_me(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    plan = get_active_plan(session, current_user.id)
    usage = get_or_create_usage(session, current_user.id)
    return {
        "plan": {
            "slug": plan.slug,
            "name": plan.name,
            "price_monthly": float(plan.price_monthly or 0.0) if plan.price_monthly is not None else None,
            "currency": plan.currency,
            "is_default_free": plan.is_default_free,
            "limits": plan.limits or {},
        },
        "usage": {
            "period": usage.period,
            "debates_created": usage.debates_created,
            "exports_count": usage.exports_count,
            "tokens_used": usage.tokens_used,
        },
    }


@router.post("/checkout")
def create_checkout(
    body: CheckoutRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == body.plan_slug)).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan not found")
    provider = get_billing_provider()
    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, current_user.id)
    checkout_url = provider.create_checkout_session(user_uuid, plan)
    return {"checkout_url": checkout_url}


@router.post("/webhook/{provider}")
async def billing_webhook(provider: str, request: Request):
    provider_name = provider.lower()
    headers = dict(request.headers)
    raw_body = await request.body()

    if provider_name == "stripe":
        payload: Optional[Dict] = None
        if settings.STRIPE_WEBHOOK_VERIFY and settings.STRIPE_WEBHOOK_SECRET:
            sig_header = headers.get("stripe-signature")
            if not sig_header:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing stripe signature")
            try:
                event = stripe.Webhook.construct_event(
                    raw_body,
                    sig_header,
                    settings.STRIPE_WEBHOOK_SECRET,
                )
                payload = event.to_dict_recursive() if hasattr(event, "to_dict_recursive") else dict(event)
            except Exception as exc:  # pragma: no cover - external dependency
                logger.warning("Stripe webhook signature invalid: %s", exc)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid signature") from exc
        else:
            if settings.STRIPE_WEBHOOK_VERIFY and not settings.STRIPE_WEBHOOK_SECRET:
                logger.warning("STRIPE_WEBHOOK_VERIFY enabled but STRIPE_WEBHOOK_SECRET missing; skipping verification.")
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else None
            except json.JSONDecodeError:
                logger.warning("Stripe webhook received non-JSON payload during dev mode")
                payload = None

        get_billing_provider().handle_webhook(payload or {}, headers)
        return {"status": "ok"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider not supported")


billing_router = router
