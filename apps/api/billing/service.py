from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Union

from fastapi import HTTPException, status
from sqlmodel import Session, select

from .models import BillingPlan, BillingSubscription, BillingUsage
from integrations.events import emit_event

UserID = Union[str, uuid.UUID]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_user_id(user_id: UserID) -> str:
    return str(user_id)


def _current_period() -> str:
    return _now().strftime("%Y-%m")


def get_active_plan(db: Session, user_id: UserID) -> BillingPlan:
    uid = _normalize_user_id(user_id)
    now = _now()
    stmt = (
        select(BillingSubscription)
        .where(
            BillingSubscription.user_id == uid,
            BillingSubscription.status == "active",
            BillingSubscription.current_period_end >= now,
        )
        .order_by(BillingSubscription.current_period_end.desc())
    )
    subscription = db.exec(stmt).first()
    if subscription:
        plan_ref = db.get(BillingPlan, subscription.plan_id)
        if plan_ref:
            return plan_ref

    plan_stmt = select(BillingPlan).where(BillingPlan.is_default_free.is_(True))
    plan = db.exec(plan_stmt).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="default billing plan missing")
    return plan


def get_or_create_usage(db: Session, user_id: UserID, period: Optional[str] = None) -> BillingUsage:
    uid = _normalize_user_id(user_id)
    period_value = period or _current_period()
    stmt = select(BillingUsage).where(BillingUsage.user_id == uid, BillingUsage.period == period_value)
    usage = db.exec(stmt).first()
    if not usage:
        usage = BillingUsage(user_id=uid, period=period_value)
        db.add(usage)
        db.flush()
    return usage


def check_limits_and_raise(db: Session, user_id: UserID, usage: BillingUsage) -> None:
    plan = get_active_plan(db, user_id)
    limits: Dict[str, object] = plan.limits or {}

    def _as_int(value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    max_debates = _as_int(limits.get("max_debates_per_month"))
    if max_debates is not None and usage.debates_created > max_debates:
        emit_event(
            "usage_limit_exceeded",
            {"user_id": _normalize_user_id(user_id), "metric": "debates", "limit": max_debates},
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "BILLING_LIMIT_DEBATES", "max": max_debates},
        )

    exports_flag = limits.get("exports_enabled", True)
    exports_allowed = not (
        exports_flag in {False, "false", "False", "0", 0}
    )
    if not exports_allowed and usage.exports_count > 0:
        emit_event(
            "usage_limit_exceeded",
            {"user_id": _normalize_user_id(user_id), "metric": "exports"},
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "BILLING_LIMIT_EXPORTS_DISABLED"},
        )


def _maybe_emit_nearing(user_id: UserID, metric: str, used: int, limit: Optional[int]) -> None:
    if not limit or limit <= 0:
        return
    threshold = max(1, int(limit * 0.8))
    if used == threshold:
        emit_event(
            "usage_limit_nearing",
            {"user_id": _normalize_user_id(user_id), "metric": metric, "current": used, "limit": limit},
        )


def increment_debate_usage(db: Session, user_id: UserID) -> BillingUsage:
    usage = get_or_create_usage(db, user_id)
    usage.debates_created += 1
    usage.last_updated_at = _now()
    check_limits_and_raise(db, user_id, usage)
    plan = get_active_plan(db, user_id)
    max_debates = plan.limits.get("max_debates_per_month")
    try:
        limit_int = int(max_debates) if max_debates is not None else None
    except (TypeError, ValueError):
        limit_int = None
    _maybe_emit_nearing(user_id, "debates", usage.debates_created, limit_int)
    return usage


def increment_export_usage(db: Session, user_id: UserID) -> BillingUsage:
    usage = get_or_create_usage(db, user_id)
    usage.exports_count += 1
    usage.last_updated_at = _now()
    check_limits_and_raise(db, user_id, usage)
    return usage


def add_tokens_usage(db: Session, user_id: UserID, model_id: str, tokens: int) -> BillingUsage:
    usage = get_or_create_usage(db, user_id)
    usage.tokens_used += int(tokens)
    model_totals = dict(usage.model_tokens or {})
    model_totals[model_id] = int(model_totals.get(model_id, 0)) + int(tokens)
    usage.model_tokens = model_totals
    usage.last_updated_at = _now()
    return usage
