from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from auth import get_current_admin
from billing.models import BillingPlan, BillingSubscription
from deps import get_session
from fastapi import APIRouter, Depends
from models import AuditLog, Debate, LLMUsageLog, User
from routes.admin.referrals import build_referral_metrics
from sqlalchemy import func
from sqlmodel import Session, select

router = APIRouter()

_COMPLETED_STATUSES = ("completed", "completed_with_warnings")
_IN_PROGRESS_STATUSES = ("queued", "running", "scheduled", "perspectives_ready")


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
    """Get live system metrics: Activation, PLG/Sharing, Billing, Economics."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # 1. Activation / retention proxies based on durable decision-run creation.
    dau = _distinct_active_users(session, day_ago)
    wau = _distinct_active_users(session, week_ago)
    mau = _distinct_active_users(session, month_ago)

    runs_created_24h = int(
        session.exec(
            select(func.count(Debate.id)).where(Debate.created_at >= day_ago)
        ).one()
        or 0
    )
    in_progress_runs = int(
        session.exec(
            select(func.count(Debate.id)).where(Debate.status.in_(_IN_PROGRESS_STATUSES))
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

    # Generic public-view audit count remains useful as an engagement event
    # count, but acquisition attribution is exclusively token based. Public-view
    # audit rows intentionally no longer persist visitor IPs.
    shared_views_count = int(
        session.exec(
            select(func.count(AuditLog.id))
            .where(AuditLog.action == "view_shared_debate")
            .where(AuditLog.created_at >= month_ago)
        ).one()
        or 0
    )
    referral_metrics = build_referral_metrics(session)

    # 3. Billing conversion and MRR.
    total_users = int(session.exec(select(func.count(User.id))).one() or 0)
    legacy_free_markers = int(
        session.exec(select(func.count(User.id)).where(User.plan == "free")).one() or 0
    )
    legacy_pro_markers = int(
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
    # Trialing rows are intentionally excluded from paid MRR/conversion.
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
            "runs_created_24h": runs_created_24h,
            "in_progress_runs": in_progress_runs,
            # Compatibility alias: historically this field mixed all 24h-created
            # runs with in-progress runs. It now means genuinely in-progress.
            "active_debates": in_progress_runs,
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
            "referral_issued_links_30d": referral_metrics["issued_links"],
            "referral_visited_links_30d": referral_metrics["visited_links"],
            "referral_total_views_30d": referral_metrics["total_views"],
            "referred_signups": referral_metrics["claimed_signups"],
            "referred_signups_30d": referral_metrics["claimed_signups"],
            "conversion_rate": referral_metrics["conversion_rate"],
            "conversion_rate_30d": referral_metrics["conversion_rate"],
            "visit_rate_30d": referral_metrics["visit_rate"],
            "attribution_method": referral_metrics["attribution_method"],
            "uses_visitor_ip": False,
            "stores_raw_token": False,
            # Deprecated compatibility keys. New public-view audit rows do not
            # retain IP and canonical acquisition metrics never use IP identity.
            "shared_view_ips_30d": 0,
            "referred_signup_ips_30d": 0,
        },
        "billing_conversion": {
            "total_users": total_users,
            # Compatibility counters only; do not treat User.plan as paid truth.
            "free_users": legacy_free_markers,
            "pro_users": legacy_pro_markers,
            "legacy_free_plan_markers": legacy_free_markers,
            "legacy_pro_plan_markers": legacy_pro_markers,
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
            "active_debates": "currently in-progress decision runs only; runs_created_24h is reported separately",
            "north_star": "weekly completed decision runs that are currently public/shareable",
            "share_rate_window_days": 7,
            "referral_attribution_window_days": referral_metrics["window_days"],
            "referral_attribution_note": "Canonical acquisition attribution uses one-way-hashed high-entropy referral tokens. Public-view audit events do not retain visitor IP and IP identity is not used for conversion.",
            "billing_marker_note": "User.plan counts are compatibility markers only; active_paid_users/subscriptions and MRR come from canonical BillingSubscription rows.",
            "mrr_note": "Only positive-priced ACTIVE subscriptions whose billing period contains now are counted; trialing is excluded. Currencies are not FX-converted; estimated_mrr is USD-only.",
            "unit_economics_window_days": 30,
        },
    }
