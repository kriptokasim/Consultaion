from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace
from typing import Dict, List, Optional

from auth import get_current_user
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models import User
from parliament.model_registry import get_model_info
from pydantic import BaseModel
from sqlmodel import Session, select

from .models import BillingPlan, BillingUsage
from .providers import get_billing_provider
from .reconciliation import (
    get_reconciliation_discrepancies,
    get_reconciliation_runs,
    reconcile_usage,
)
from .service import (
    _current_period,
    get_active_plan,
    get_or_create_usage,
)


def csrf_exempt(func):
    """Mark a route as exempt from CSRF protection."""
    func.csrf_exempt = True
    return func


def _emit_post_commit_events(payload: dict) -> None:
    """Emit billing events only after the webhook transaction has committed.

    FH125: Side effects must not occur if the DB commit fails.
    """
    from integrations.events import emit_event

    event_type = payload.get("type", "")
    data = (payload.get("data") or {}).get("object") or {}
    metadata = data.get("metadata") or {}

    if event_type == "checkout.session.completed":
        user_id = metadata.get("user_id")
        plan_slug = metadata.get("plan_slug")
        if user_id and plan_slug:
            emit_event(
                "subscription_activated",
                {"user_id": user_id, "plan_slug": plan_slug, "provider": "stripe"},
            )
    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        if subscription_id:
            emit_event(
                "subscription_cancelled",
                {"subscription_id": subscription_id, "provider": "stripe"},
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
    cfg = get_model_info(model_id)
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
    from security.owner import is_owner
    return {
        "is_owner": is_owner(current_user),
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


@csrf_exempt
@router.post("/webhook/{provider}")
async def billing_webhook(
    provider: str,
    request: Request,
    session: Session = Depends(get_session),
):
    provider_name = provider.lower()
    headers = dict(request.headers)
    raw_body = await request.body()

    if provider_name == "stripe":
        payload: Optional[Dict] = None
        if settings.STRIPE_WEBHOOK_VERIFY:
            secret = settings.STRIPE_WEBHOOK_SECRET
            if not secret:
                logger.error("Stripe webhook verification enabled but STRIPE_WEBHOOK_SECRET is missing")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="stripe webhook misconfigured",
                )
            sig_header = headers.get("stripe-signature")
            if not sig_header:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing stripe signature")
            try:
                event = stripe.Webhook.construct_event(
                    raw_body,
                    sig_header,
                    secret,
                )
                payload = event.to_dict_recursive() if hasattr(event, "to_dict_recursive") else dict(event)
            except Exception as exc:  # pragma: no cover - external dependency
                logger.warning("Stripe webhook signature invalid: %s", exc)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid signature") from exc
        else:
            if not settings.STRIPE_WEBHOOK_INSECURE_DEV:
                logger.error(
                    "Stripe webhook verification disabled without STRIPE_WEBHOOK_INSECURE_DEV=1; rejecting payload"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="stripe webhook verification disabled",
                )
            logger.info("Processing unsigned Stripe webhook in insecure dev mode")
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else None
            except json.JSONDecodeError:
                logger.warning("Stripe webhook received non-JSON payload during dev mode")
                payload = None
        import inspect
        provider = get_billing_provider()
        sig = inspect.signature(provider.handle_webhook)

        # OT-10: Wrap webhook handler in explicit DB transaction for atomicity
        # If the handler fails midway, the entire webhook is rolled back
        # and Stripe will retry on the next delivery attempt.
        from database import session_scope
        with session_scope() as tx_session:
            try:
                if "db_session" in sig.parameters:
                    provider.handle_webhook(payload or {}, headers, db_session=tx_session)
                else:
                    provider.handle_webhook(payload or {}, headers)
            except Exception as exc:
                logger.error(
                    "Webhook handler failed (transaction rolled back): provider=%s event_type=%s error=%s",
                    provider_name,
                    (payload or {}).get("type", "unknown"),
                    exc,
                )
                from observability.metrics import record_billing_webhook
                record_billing_webhook(provider_name, (payload or {}).get("type", "unknown"), "error")
                raise

        # Emit side effects only after durable commit
        _emit_post_commit_events(payload or {})

        from observability.metrics import record_billing_webhook
        record_billing_webhook(provider_name, (payload or {}).get("type", "unknown"), "ok")
        return {"status": "ok"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider not supported")


# ── Admin Reconciliation Endpoints ──────────────────────────────────────────

@router.get("/admin/reconciliation/runs")
def admin_list_reconciliation_runs(
    limit: int = 10,
    period: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List recent reconciliation runs (admin only)."""
    from security.owner import is_owner
    if not is_owner(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    runs = get_reconciliation_runs(session, limit=limit, period=period)
    return {"items": runs}


@router.get("/admin/reconciliation/runs/{run_id}/discrepancies")
def admin_get_reconciliation_discrepancies(
    run_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get discrepancies for a specific reconciliation run (admin only)."""
    from security.owner import is_owner
    if not is_owner(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    import uuid as _uuid
    try:
        run_uuid = _uuid.UUID(run_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid run_id") from err
    discs = get_reconciliation_discrepancies(session, run_uuid)
    return {"items": discs}


@router.post("/admin/reconciliation/run")
def admin_trigger_reconciliation(
    period: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a reconciliation run (admin only)."""
    from security.owner import is_owner
    if not is_owner(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    report = reconcile_usage(db=session, period=period, run_type="manual")
    return report


billing_router = router
