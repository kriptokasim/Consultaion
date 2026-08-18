from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from auth import get_current_admin
from billing.models import BillingPlan, BillingSubscription
from deps import get_session
from fastapi import APIRouter, Depends
from models import AuditLog, Debate, LLMUsageLog, User
from sqlalchemy import func
from sqlmodel import Session, select

router = APIRouter()

_COMPLETED_STATUSES = ("completed", "completed_with_warnings")
_REFERRAL_ATTRIBUTION_WINDOW = timedelta(days=7)


def _distinct_active_users(session: Session, since: datetime) -> int:
    """Count users who created a decision run in the requested window.

    Debate rows are durable product facts and are therefore a safer investor KPI
    source than best-effort audit events, which can be intentionally sparse.
    """
    return int(
        session.exec(
            select(func.count(func.distinct(Debate.user_id)))
            .where(Debate.created_at >= since)
            .where(Debate.user_id.is_not(None))
        ).one()
        or 0
    )


def _is_public_config(config: dict | None) -> bool:
    return bool(config and config.get("is_public") is True)


@router.get("/metrics")
def admin_metrics(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """Return investor-grade product, growth, billing, cost, and quality metrics.

    The endpoint intentionally exposes metric definitions alongside values so
    diligence dashboards do not silently mix incompatible windows or currencies.
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # 1. Activation / retention proxies based on durable decision-run creation.
    dau = _distinct_active_users(session, day_ago)
    wau = _distinct_active_users(session, week_ago)
    mau = _distinct_active_users(session, month_ago)

    active_debates_count = int(
        session.exec(
            select(func.count(Debate.id)).where(
                (Debate.created_at >= day_ago)
                | (Debate.status.in_(["queued", "running", "scheduled", "perspectives_ready"]))
            )
        ).one()
        or 0
    )

    completed_runs_7d = int(
        session.exec(
            select(func.count(Debate.id))
            .where(Debate.created_at >= week_ago)
            .where(Debate.status.in_(_COMPLETED_STATUSES))
        ).one()
        or 0
    )
    completed_runs_30d = int(
        session.exec(
            select(func.count(Debate.id))
            .where(Debate.created_at >= month_ago)
            .where(Debate.status.in_(_COMPLETED_STATUSES))
        ).one()
        or 0
    )

    # 2. PLG / sharing.
    # Scope the North Star numerator to the same weekly completion cohort so
    # share rate cannot exceed 100% merely because an old run was shared today.
    weekly_completed_rows = session.exec(
        select(Debate.id, Debate.config)
        .where(Debate.created_at >= week_ago)
        .where(Debate.status.in_(_COMPLETED_STATUSES))
    ).all()
    weekly_shareable_artifacts = sum(
        1 for _debate_id, config in weekly_completed_rows if _is_public_config(config)
    )
    share_rate_7d = (
        weekly_shareable_artifacts / completed_runs_7d * 100.0
        if completed_runs_7d > 0
        else 0.0
    )

    # Keep the all-time public count for backward compatibility, but do not use
    # it as an investor share-rate numerator.
    all_configs = session.exec(select(Debate.config)).all()
    public_debates_count = sum(1 for config in all_configs if _is_public_config(config))

    share_event_rows = session.exec(
        select(AuditLog.target_id, AuditLog.meta)
        .where(AuditLog.action == "debate_shared")
        .where(AuditLog.created_at >= week_ago)
    ).all()
    weekly_share_enable_ids = {
        target_id
        for target_id, meta in share_event_rows
        if target_id and meta and meta.get("is_public") is True
    }

    shared_views_count = int(
        session.exec(
            select(func.count(AuditLog.id))
            .where(AuditLog.action == "view_shared_debate")
            .where(AuditLog.created_at >= month_ago)
        ).one()
        or 0
    )

    # Referral attribution is currently an IP-based proxy. Bound it to a
    # seven-day lookback so an ancient view cannot claim an unrelated signup.
    signup_logs = session.exec(
        select(AuditLog.created_at, AuditLog.meta)
        .where(AuditLog.action.in_(["register", "register_google"]))
        .where(AuditLog.created_at >= month_ago)
    ).all()
    view_logs = session.exec(
        select(AuditLog.created_at, AuditLog.meta)
        .where(AuditLog.action == "view_shared_debate")
        .where(AuditLog.created_at >= month_ago - _REFERRAL_ATTRIBUTION_WINDOW)
    ).all()

    ip_views: dict[str, list[datetime]] = defaultdict(list)
    for created_at, meta in view_logs:
        ip_address = meta.get("ip_address") if meta else None
        if ip_address:
            ip_views[ip_address].append(created_at)

    referred_signups_count = 0
    for signup_time, meta in signup_logs:
        signup_ip = meta.get("ip_address") if meta else None
        if not signup_ip or signup_ip not in ip_views:
            continue
        earliest = signup_time - _REFERRAL_ATTRIBUTION_WINDOW
        if any(earliest <= view_time < signup_time for view_time in ip_views[signup_ip]):
            referred_signups_count += 1

    referral_conversion_rate_30d = (
        referred_signups_count / shared_views_count * 100.0
        if shared_views_count > 0
        else 0.0
    )

    # 3. Billing conversion and MRR.
    total_users = int(session.exec(select(func.count(User.id))).one() or 0)
    free_users = int(
        session.exec(select(func.count(User.id)).where(User.plan == "free")).one() or 0
    )
    pro_users = int(
        session.exec(select(func.count(User.id)).where(User.plan == "pro")).one() or 0
    )

    status_counts = session.exec(
        select(BillingSubscription.status, func.count(BillingSubscription.id)).group_by(
            BillingSubscription.status
        )
    ).all()
    subscription_status_breakdown = {
        status: int(count) for status, count in status_counts
    }

    # Resolve the actual plan for each paid subscription. Status alone is not
    # sufficient: stale webhook state can leave an expired row marked active.
    active_subscription_rows = session.exec(
        select(
            BillingSubscription.user_id,
            BillingPlan.slug,
            BillingPlan.price_monthly,
            BillingPlan.currency,
        )
        .join(BillingPlan, BillingSubscription.plan_id == BillingPlan.id)
        .where(BillingSubscription.status == "active")
        .where(BillingSubscription.current_period_start <= now)
        .where(BillingSubscription.current_period_end > now)
    ).all()

    mrr_by_currency: dict[str, float] = defaultdict(float)
    active_paid_user_ids: set[str] = set()
    active_paid_subscriptions = 0
    for user_id, _plan_slug, price_monthly, currency in active_subscription_rows:
        price = float(price_monthly or 0.0)
        if price <= 0:
            continue
        active_paid_subscriptions += 1
        active_paid_user_ids.add(user_id)
        mrr_by_currency[currency or "UNKNOWN"] += price

    active_paid_users = len(active_paid_user_ids)
    paid_conversion_rate = (
        active_paid_users / total_users * 100.0 if total_users > 0 else 0.0
    )

    # Legacy key remains USD-only instead of silently summing unlike currencies.
    estimated_mrr_usd = float(mrr_by_currency.get("USD", 0.0))

    # 4. Unit economics.
    cumulative_llm_cost = float(
        session.exec(select(func.sum(LLMUsageLog.cost_usd))).one() or 0.0
    )
    llm_cost_30d = float(
        session.exec(
            select(func.sum(LLMUsageLog.cost_usd)).where(
                LLMUsageLog.created_at >= month_ago
            )
        ).one()
        or 0.0
    )

    completed_run_llm_cost_30d = float(
        session.exec(
            select(func.sum(LLMUsageLog.cost_usd))
            .select_from(LLMUsageLog)
            .join(Debate, Debate.id == LLMUsageLog.debate_id)
            .where(Debate.created_at >= month_ago)
            .where(Debate.status.in_(_COMPLETED_STATUSES))
        ).one()
        or 0.0
    )
    cost_per_completed_run_30d = (
        completed_run_llm_cost_30d / completed_runs_30d
        if completed_runs_30d > 0
        else 0.0
    )

    provider_costs_30d = session.exec(
        select(LLMUsageLog.provider, func.sum(LLMUsageLog.cost_usd))
        .where(LLMUsageLog.created_at >= month_ago)
        .group_by(LLMUsageLog.provider)
    ).all()
    provider_cost_breakdown_30d = {
        provider: float(cost or 0.0) for provider, cost in provider_costs_30d
    }

    provider_costs_all_time = session.exec(
        select(LLMUsageLog.provider, func.sum(LLMUsageLog.cost_usd)).group_by(
            LLMUsageLog.provider
        )
    ).all()
    provider_cost_breakdown = {
        provider: float(cost or 0.0) for provider, cost in provider_costs_all_time
    }

    # 5. AI quality / reliability.
    model_calls_30d = int(
        session.exec(
            select(func.count(LLMUsageLog.id)).where(LLMUsageLog.created_at >= month_ago)
        ).one()
        or 0
    )
    failed_model_calls_30d = int(
        session.exec(
            select(func.count(LLMUsageLog.id))
            .where(LLMUsageLog.created_at >= month_ago)
            .where(LLMUsageLog.success.is_(False))
        ).one()
        or 0
    )
    fallback_calls_30d = int(
        session.exec(
            select(func.count(LLMUsageLog.id))
            .where(LLMUsageLog.created_at >= month_ago)
            .where(LLMUsageLog.fallback_used.is_(True))
        ).one()
        or 0
    )
    retried_calls_30d = int(
        session.exec(
            select(func.count(LLMUsageLog.id))
            .where(LLMUsageLog.created_at >= month_ago)
            .where(LLMUsageLog.retry_count > 0)
        ).one()
        or 0
    )
    total_tokens_30d = int(
        session.exec(
            select(func.sum(LLMUsageLog.total_tokens)).where(
                LLMUsageLog.created_at >= month_ago
            )
        ).one()
        or 0
    )
    latency_values = session.exec(
        select(LLMUsageLog.latency_ms)
        .where(LLMUsageLog.created_at >= month_ago)
        .where(LLMUsageLog.latency_ms.is_not(None))
    ).all()
    median_latency_ms_30d = float(median(latency_values)) if latency_values else 0.0

    model_failure_rate_30d = (
        failed_model_calls_30d / model_calls_30d * 100.0
        if model_calls_30d > 0
        else 0.0
    )
    fallback_rate_30d = (
        fallback_calls_30d / model_calls_30d * 100.0
        if model_calls_30d > 0
        else 0.0
    )
    retry_rate_30d = (
        retried_calls_30d / model_calls_30d * 100.0
        if model_calls_30d > 0
        else 0.0
    )

    return {
        "activation": {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "active_debates": active_debates_count,
            "completed_runs_7d": completed_runs_7d,
            "completed_runs_30d": completed_runs_30d,
        },
        "plg_sharing": {
            "public_debates": public_debates_count,
            "weekly_shareable_artifacts": weekly_shareable_artifacts,
            "weekly_share_enable_events": len(weekly_share_enable_ids),
            "share_rate_7d": share_rate_7d,
            "shared_views": shared_views_count,
            "shared_views_30d": shared_views_count,
            "referred_signups": referred_signups_count,
            "referred_signups_30d": referred_signups_count,
            "conversion_rate": referral_conversion_rate_30d,
            "conversion_rate_30d": referral_conversion_rate_30d,
            "attribution_method": "ip_7d_proxy",
        },
        "billing_conversion": {
            "total_users": total_users,
            "free_users": free_users,
            "pro_users": pro_users,
            "active_paid_users": active_paid_users,
            "active_paid_subscriptions": active_paid_subscriptions,
            "conversion_rate": paid_conversion_rate,
            "subscription_statuses": subscription_status_breakdown,
        },
        "economics": {
            "estimated_mrr": estimated_mrr_usd,
            "estimated_mrr_usd": estimated_mrr_usd,
            "mrr_by_currency": dict(mrr_by_currency),
            "cumulative_llm_cost": cumulative_llm_cost,
            "llm_cost_30d": llm_cost_30d,
            "completed_run_llm_cost_30d": completed_run_llm_cost_30d,
            "cost_per_completed_run_30d": cost_per_completed_run_30d,
            "provider_cost_breakdown": provider_cost_breakdown,
            "provider_cost_breakdown_30d": provider_cost_breakdown_30d,
        },
        "ai_quality": {
            "model_calls_30d": model_calls_30d,
            "failed_model_calls_30d": failed_model_calls_30d,
            "model_failure_rate_30d": model_failure_rate_30d,
            "fallback_calls_30d": fallback_calls_30d,
            "fallback_rate_30d": fallback_rate_30d,
            "retried_calls_30d": retried_calls_30d,
            "retry_rate_30d": retry_rate_30d,
            "median_latency_ms_30d": median_latency_ms_30d,
            "total_tokens_30d": total_tokens_30d,
        },
        "definitions": {
            "activity_source": "distinct users creating debate/decision runs",
            "north_star": "weekly completed decision runs that are currently public/shareable",
            "share_rate_window_days": 7,
            "referral_attribution_window_days": 7,
            "referral_attribution_note": "IP-based proxy; replace with explicit referral/session identifiers before external reporting.",
            "mrr_note": "Only positive-priced subscriptions whose active billing period contains now are counted. Currencies are not FX-converted; estimated_mrr is USD-only.",
            "unit_economics_window_days": 30,
        },
    }
