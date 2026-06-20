from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from auth import get_current_admin
from billing.models import BillingPlan, BillingSubscription
from deps import get_session
from fastapi import APIRouter, Depends
from models import AuditLog, Debate, LLMUsageLog, User
from sqlalchemy import func
from sqlmodel import Session, select

router = APIRouter()


@router.get("/metrics")
def admin_metrics(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    Get live system metrics: Activation, PLG/Sharing, Billing, and Economics.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)

    # 1. Activation Metrics
    daus = session.exec(
        select(func.count(func.distinct(AuditLog.user_id)))
        .where(AuditLog.created_at >= day_ago)
        .where(AuditLog.user_id is not None)
    ).one() or 0

    active_debates_count = session.exec(
        select(func.count(Debate.id))
        .where((Debate.created_at >= day_ago) | (Debate.status.in_(["queued", "running", "scheduled"])))
    ).one() or 0

    # 2. PLG/Sharing Metrics
    all_configs = session.exec(select(Debate.config)).all()
    public_debates_count = sum(1 for cfg in all_configs if cfg and cfg.get("is_public") is True)

    shared_views_count = session.exec(
        select(func.count(AuditLog.id))
        .where(AuditLog.action == "view_shared_debate")
    ).one() or 0

    signup_logs = session.exec(
        select(AuditLog)
        .where(AuditLog.action.in_(["register", "register_google"]))
    ).all()

    view_logs = session.exec(
        select(AuditLog)
        .where(AuditLog.action == "view_shared_debate")
    ).all()

    ip_views = defaultdict(list)
    for log in view_logs:
        ip = log.meta.get("ip_address") if log.meta else None
        if ip:
            ip_views[ip].append(log.created_at)

    referred_signups_count = 0
    for signup in signup_logs:
        signup_ip = signup.meta.get("ip_address") if signup.meta else None
        if signup_ip and signup_ip in ip_views:
            signup_time = signup.created_at
            if any(vt < signup_time for vt in ip_views[signup_ip]):
                referred_signups_count += 1

    # 3. Billing Conversion Metrics
    total_users = session.exec(select(func.count(User.id))).one() or 0
    free_users = session.exec(select(func.count(User.id)).where(User.plan == "free")).one() or 0
    pro_users = session.exec(select(func.count(User.id)).where(User.plan == "pro")).one() or 0

    status_counts = session.exec(
        select(BillingSubscription.status, func.count(BillingSubscription.id))
        .group_by(BillingSubscription.status)
    ).all()
    subscription_status_breakdown = {status: count for status, count in status_counts}

    # 4. Economic Metrics
    total_provider_cost = session.exec(select(func.sum(LLMUsageLog.cost_usd))).one() or 0.0

    pro_plan = session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    pro_price = float(pro_plan.price_monthly or 15.00) if pro_plan else 15.00

    active_pro_subs = session.exec(
        select(func.count(BillingSubscription.id))
        .where(BillingSubscription.status == "active")
    ).one() or 0
    estimated_mrr = active_pro_subs * pro_price

    provider_costs = session.exec(
        select(LLMUsageLog.provider, func.sum(LLMUsageLog.cost_usd))
        .group_by(LLMUsageLog.provider)
    ).all()
    provider_cost_breakdown = {prov: float(cost or 0.0) for prov, cost in provider_costs}

    return {
        "activation": {
            "dau": daus,
            "active_debates": active_debates_count,
        },
        "plg_sharing": {
            "public_debates": public_debates_count,
            "shared_views": shared_views_count,
            "referred_signups": referred_signups_count,
            "conversion_rate": (referred_signups_count / shared_views_count * 100.0) if shared_views_count > 0 else 0.0,
        },
        "billing_conversion": {
            "total_users": total_users,
            "free_users": free_users,
            "pro_users": pro_users,
            "conversion_rate": (pro_users / total_users * 100.0) if total_users > 0 else 0.0,
            "subscription_statuses": subscription_status_breakdown,
        },
        "economics": {
            "estimated_mrr": estimated_mrr,
            "cumulative_llm_cost": float(total_provider_cost or 0.0),
            "provider_cost_breakdown": provider_cost_breakdown,
        },
    }
