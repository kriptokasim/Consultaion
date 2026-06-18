from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from auth import get_current_admin
from billing.models import BillingPlan, BillingSubscription, BillingUsage
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, Query
from models import User
from sqlmodel import Session, select

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

    # Prefetch active plans, subscriptions, and usages
    from billing.models import BillingPlan, BillingSubscription, BillingUsage
    from security.owner import is_owner
    from collections import defaultdict

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
                BillingSubscription.status == "active",
                BillingSubscription.current_period_end >= now,
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
        # Get current period usage
        current_usage = user_latest_usage_map.get(user.id)
        
        # Get 7-day usage history
        usage_history = user_history_map.get(user.id, [])
        
        # Calculate 7-day totals
        tokens_7d = sum(u.tokens_used for u in usage_history)
        exports_7d = sum(u.exports_count for u in usage_history)
        debates_7d = sum(u.debates_created for u in usage_history)
        
        # Resolve active plan in-memory
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


@router.get("/usage/quota")
def admin_quota_usage(
    email: Optional[str] = Query(None, description="Filter by email"),
    plan: Optional[str] = Query(None, description="Filter by plan (free/pro/internal)"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    View user quota usage with plan limits.
    
    Shows tokens and exports used today vs daily limits for each user.
    Useful for monitoring and troubleshooting quota issues.
    """
    from plan_config import get_plan_limits
    from usage_limits import get_today_usage
    
    # Build query
    query = select(User)
    if email:
        query = query.where(User.email.contains(email))
    if plan:
        query = query.where(User.plan == plan)
    
    users = session.exec(query.limit(limit)).all()
    
    results = []
    for user in users:
        usage = get_today_usage(session, user.id)
        limits = get_plan_limits(user.plan)
        
        results.append({
            "user_id": user.id,
            "email": user.email,
            "plan": user.plan,
            "tokens_used_today": usage["tokens_used"],
            "daily_token_limit": limits.daily_token_limit,
            "token_usage_pct": round(usage["tokens_used"] / limits.daily_token_limit * 100, 1),
            "exports_used_today": usage["exports_used"],
            "daily_export_limit": limits.daily_export_limit,
            "export_usage_pct": round(usage["exports_used"] / limits.daily_export_limit * 100, 1) if limits.daily_export_limit > 0 else 0,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        })
    
    return {"users": results, "total": len(results)}
