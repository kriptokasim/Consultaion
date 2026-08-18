from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from auth import get_current_admin
from billing.models import BillingPlan, BillingSubscription, BillingUsage
from billing.service import get_active_plan
from deps import get_session
from fastapi import APIRouter, Depends, Query
from models import User
from sqlmodel import Session, select

from config import settings
from routes.admin.dependencies import _plan_payload

router = APIRouter()


@router.get("/usage")
def admin_usage_overview(
    user_id: Optional[str] = Query(None, description="Filter by specific user ID"),
    email: Optional[str] = Query(None, description="Search by email"),  
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Admin endpoint to view user usage statistics (tokens, exports, debates) with 7-day history."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    
    # Get users to display
    users_query = select(User)
    if user_id:
        users_query = users_query.where(User.id == user_id)
    elif email:
        users_query = users_query.where(User.email.contains(email))
    
    users = session.exec(users_query.order_by(User.created_at.desc())).all()

    # Prefetch canonical plans, entitled subscriptions, and usages.
    from security.owner import is_owner

    plans = session.exec(select(BillingPlan)).all()
    plan_map = {p.id: p for p in plans}
    slug_map = {p.slug: p for p in plans}
    default_free_plan = next((p for p in plans if p.is_default_free), None)

    user_ids = [u.id for u in users]

    user_sub_map = {}
    if user_ids:
        subscriptions = session.exec(
            select(BillingSubscription)
            .where(
                BillingSubscription.user_id.in_(user_ids),
                BillingSubscription.status.in_(["active", "trialing"]),
                BillingSubscription.current_period_start <= now,
                BillingSubscription.current_period_end > now,
            )
            .order_by(BillingSubscription.current_period_end.desc())
        ).all()
        for sub in subscriptions:
            if sub.user_id not in user_sub_map:
                user_sub_map[sub.user_id] = sub

    user_latest_usage_map = {}
    user_history_map = defaultdict(list)
    if user_ids:
        all_usages = session.exec(
            select(BillingUsage)
            .where(BillingUsage.user_id.in_(user_ids))
            .order_by(BillingUsage.period.desc())
        ).all()
        for usage in all_usages:
            if usage.user_id not in user_latest_usage_map:
                user_latest_usage_map[usage.user_id] = usage
            if usage.last_updated_at and usage.last_updated_at >= seven_days_ago:
                user_history_map[usage.user_id].append(usage)
    
    items = []
    for user in users:
        current_usage = user_latest_usage_map.get(user.id)
        usage_history = user_history_map.get(user.id, [])
        tokens_7d = sum(u.tokens_used for u in usage_history)
        exports_7d = sum(u.exports_count for u in usage_history)
        debates_7d = sum(u.debates_created for u in usage_history)
        
        # Resolve active plan in-memory using the same status/window semantics
        # as billing.service.get_active_plan().
        plan = None
        if is_owner(user):
            owner_slug = settings.OWNER_PLAN
            plan = slug_map.get(owner_slug) or default_free_plan
        else:
            sub = user_sub_map.get(user.id)
            if sub:
                plan = plan_map.get(sub.plan_id)
            if not plan:
                plan = default_free_plan
        
        items.append({
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "current_period": {
                "period": current_usage.period if current_usage else None,
                "tokens_used": current_usage.tokens_used if current_usage else 0,
                "exports_count": current_usage.exports_count if current_usage else 0,
                "debates_created": current_usage.debates_created if current_usage else 0,
                "model_tokens": current_usage.model_tokens if current_usage else {},
            },
            "last_7_days": {
                "tokens_total": tokens_7d,
                "exports_total": exports_7d,
                "debates_total": debates_7d,
            },
            "plan": _plan_payload(plan),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        })
    
    total = len(items)
    paginated = items[offset:offset + limit]
    
    return {
        "items": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _daily_limit(plan: BillingPlan, key: str, fallback: int) -> int:
    raw = (plan.limits or {}).get(key)
    if raw is None:
        return fallback
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


@router.get("/usage/quota")
def admin_quota_usage(
    user_id: Optional[str] = Query(None, description="Filter by exact user ID"),
    email: Optional[str] = Query(None, description="Filter by email"),
    plan: Optional[str] = Query(None, description="Filter by canonical plan (free/pro/internal)"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """View today's quota use against canonical entitlement limits.

    ``User.plan`` is a compatibility marker and can lag subscription expiry or
    webhook transitions. Resolve the effective BillingSubscription first, then
    apply the same static/configured limits used by runtime quota authorization.
    """
    from plan_config import get_plan_limits
    from usage_limits import get_today_usage
    
    query = select(User).order_by(User.created_at.desc())
    if user_id:
        query = query.where(User.id == user_id)
    elif email:
        query = query.where(User.email.contains(email))
    # Canonical plan is derived from subscription state, so applying SQL LIMIT
    # before resolving `plan` could drop matching users. Resolve first, then cap
    # the filtered response below.
    users = session.exec(query).all()
    
    results = []
    for user in users:
        active_plan = get_active_plan(session, user.id)
        if plan and active_plan.slug != plan:
            continue

        usage = get_today_usage(session, user.id)
        static_limits = get_plan_limits(active_plan.slug)
        token_limit = _daily_limit(
            active_plan,
            "max_tokens_per_day",
            static_limits.daily_token_limit,
        )
        export_limit = _daily_limit(
            active_plan,
            "max_exports_per_day",
            static_limits.daily_export_limit,
        )

        results.append({
            "user_id": user.id,
            "email": user.email,
            "plan": active_plan.slug,
            "legacy_plan_marker": user.plan,
            "tokens_used_today": usage["tokens_used"],
            "daily_token_limit": token_limit,
            "token_usage_pct": (
                round(usage["tokens_used"] / token_limit * 100, 1)
                if token_limit > 0 else 0
            ),
            "exports_used_today": usage["exports_used"],
            "daily_export_limit": export_limit,
            "export_usage_pct": (
                round(usage["exports_used"] / export_limit * 100, 1)
                if export_limit > 0 else 0
            ),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        })
        if len(results) >= limit:
            break
    
    return {"users": results, "total": len(results)}
