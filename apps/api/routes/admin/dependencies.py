from __future__ import annotations

from typing import Any, Dict, Optional

from billing.models import BillingPlan, BillingUsage
from models import Debate
from sqlalchemy import func
from sqlmodel import Session, select


def _latest_usage(session: Session, user_id: str) -> Optional[BillingUsage]:
    return session.exec(
        select(BillingUsage)
        .where(BillingUsage.user_id == user_id)
        .order_by(BillingUsage.period.desc())
    ).first()


def _plan_payload(plan: Optional["BillingPlan"]) -> Optional[Dict[str, Any]]:
    if not plan:
        return None
    return {
        "slug": plan.slug,
        "name": plan.name,
        "price_monthly": float(plan.price_monthly or 0.0) if plan.price_monthly is not None else None,
        "currency": plan.currency,
        "is_default_free": plan.is_default_free,
    }


def _usage_payload(usage: Optional[BillingUsage]) -> Optional[Dict[str, Any]]:
    if not usage:
        return None
    return {
        "period": usage.period,
        "debates_created": usage.debates_created,
        "exports_count": usage.exports_count,
        "tokens_used": usage.tokens_used,
        "model_tokens": usage.model_tokens or {},
        "last_updated_at": usage.last_updated_at.isoformat() if usage.last_updated_at else None,
    }


def _activity_snapshot(session: Session) -> Dict[str, Dict[str, Any]]:
    rows = session.exec(
        select(
            Debate.user_id,
            func.count(Debate.id),
            func.max(Debate.created_at),
        ).group_by(Debate.user_id)
    ).all()
    snapshot: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, tuple):
            user_id, count_value, last_activity = row
        else:
            user_id = row[0]
            count_value = row[1]
            last_activity = row[2]
        snapshot[str(user_id)] = {
            "debate_count": int(count_value or 0),
            "last_activity": last_activity.isoformat() if last_activity else None,
        }
    return snapshot
