from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from auth import get_current_admin
from billing.models import BillingPlan, BillingSubscription, BillingUsage
from billing.routes import MODEL_COST_PER_1K
from billing.service import _current_period, get_active_plan
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Query
from models import AdminEvent, AuditLog, Debate, User
from parliament.model_registry import get_default_model, list_enabled_models
from parliament.provider_health import get_provider_health_snapshot
from promotions.models import Promotion
from ratelimit import ensure_rate_limiter_ready, get_recent_429_events
from ratings import update_ratings_for_debate
from sqlalchemy import func
from sqlmodel import Session, select
from sse_backend import get_sse_backend

from routes.common import serialize_user

router = APIRouter(prefix="/admin", tags=["admin"])


def _latest_usage(session: Session, user_id: str) -> Optional[BillingUsage]:
    return session.exec(
        select(BillingUsage)
        .where(BillingUsage.user_id == user_id)
        .order_by(BillingUsage.period.desc())
    ).first()


def _plan_payload(plan: Optional[BillingPlan]) -> Optional[Dict[str, Any]]:
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


@router.get("/users")
def admin_users(
    q: Optional[str] = Query(None, description="Search by email/display name."),
    plan_slug: Optional[str] = Query(None, description="Filter users by active plan slug."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    activity = _activity_snapshot(session)
    filtered: List[Dict[str, Any]] = []
    q_lower = q.lower() if q else None
    for user in users:
        if q_lower:
            display = (user.display_name or "").lower()
            email_match = q_lower in user.email.lower()
            display_match = q_lower in display
            if not email_match and not display_match:
                continue
        plan = None
        try:
            plan = get_active_plan(session, user.id)
        except HTTPException:
            plan = None
        if plan_slug and (not plan or plan.slug != plan_slug):
            continue
        usage = _latest_usage(session, user.id)
        row = {
            **serialize_user(user),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "plan": _plan_payload(plan),
            "usage": _usage_payload(usage),
        }
        stats = activity.get(user.id, {"debate_count": 0, "last_activity": None})
        row.update(
            {
                "debate_count": stats.get("debate_count", 0),
                "last_activity": stats.get("last_activity"),
            }
        )
        filtered.append(row)
    total = len(filtered)
    items = filtered[offset : offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/users/{user_id}")
def admin_user_detail(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    plan = None
    try:
        plan = get_active_plan(session, user.id)
    except HTTPException:
        plan = None
    usage = _latest_usage(session, user.id)
    subscriptions = session.exec(
        select(BillingSubscription).where(BillingSubscription.user_id == user.id).order_by(BillingSubscription.created_at.desc())
    ).all()
    subs_payload = [
        {
            "id": str(sub.id),
            "plan_id": str(sub.plan_id),
            "status": sub.status,
            "current_period_start": sub.current_period_start.isoformat(),
            "current_period_end": sub.current_period_end.isoformat(),
            "provider": sub.provider,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
        for sub in subscriptions
    ]
    return {
        "user": serialize_user(user),
        "plan": _plan_payload(plan),
        "usage": _usage_payload(usage),
        "subscriptions": subs_payload,
    }


@router.get("/users/{user_id}/billing")
def admin_user_billing(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    plan = None
    try:
        plan = get_active_plan(session, user.id)
    except HTTPException:
        plan = None
    current_period = _current_period()
    usage = session.exec(
        select(BillingUsage).where(BillingUsage.user_id == user.id, BillingUsage.period == current_period)
    ).first()
    return {
        "plan": _plan_payload(plan),
        "usage": _usage_payload(usage),
    }


@router.get("/ops/summary")
async def admin_ops_summary(
    session: Session = Depends(get_session),
    current_admin: User = Depends(get_current_admin),
):
    _ = current_admin  # explicitly acknowledge dependency
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    def _scalar(stmt) -> int:
        row = session.exec(stmt).one()
        value = row[0] if isinstance(row, tuple) else row
        return int(value or 0)

    debates_24h = _scalar(select(func.count(Debate.id)).where(Debate.created_at >= since_24h))
    debates_7d = _scalar(select(func.count(Debate.id)).where(Debate.created_at >= since_7d))
    active_users_24h = _scalar(
        select(func.count(func.distinct(Debate.user_id))).where(
            Debate.created_at >= since_24h,
            Debate.user_id.is_not(None),
        )
    )
    tokens_24h = _scalar(
        select(func.coalesce(func.sum(BillingUsage.tokens_used), 0)).where(BillingUsage.last_updated_at >= since_24h)
    )

    model_totals: Dict[str, int] = defaultdict(int)
    for usage in session.exec(select(BillingUsage)).all():
        for model_id, amount in (usage.model_tokens or {}).items():
            model_totals[model_id] += int(amount or 0)
    top_models = sorted(model_totals.items(), key=lambda entry: entry[1], reverse=True)[:5]

    rate_limit_backend, rate_redis_ok = ensure_rate_limiter_ready()
    recent_429_events = get_recent_429_events()
    sse_backend = settings.SSE_BACKEND.lower()
    sse_redis_ok: Optional[bool] = None
    if sse_backend == "redis":
        try:
            backend = get_sse_backend()
            sse_redis_ok = await backend.ping()
        except Exception:
            sse_redis_ok = False

    models_enabled = list_enabled_models()
    seat_counts: Dict[str, int] = defaultdict(int)
    role_model_totals: Dict[tuple[str, str, str], int] = defaultdict(int)
    meta_rows = session.exec(select(Debate.final_meta)).all()
    for row in meta_rows:
        meta = row[0] if isinstance(row, tuple) else row
        if not isinstance(meta, dict):
            continue
        seat_usage = meta.get("seat_usage") or []
        for seat in seat_usage:
            if not isinstance(seat, dict):
                continue
            role = seat.get("role_profile") or seat.get("seat_name") or "seat"
            provider = seat.get("provider") or "unknown"
            model_name = seat.get("model") or "unknown"
            try:
                tokens = int(seat.get("tokens") or 0)
            except (TypeError, ValueError):
                tokens = 0
            seat_counts[role] += 1
            role_model_totals[(role, provider, model_name)] += tokens

    model_usage_by_role = [
        {
            "role": role,
            "provider": provider,
            "model": model_name,
            "total_tokens": tokens,
        }
        for (role, provider, model_name), tokens in role_model_totals.items()
    ]
    model_usage_by_role.sort(key=lambda entry: entry["total_tokens"], reverse=True)
    model_usage_by_role = model_usage_by_role[:10]

    dispatch_payload = {
        "mode": settings.DEBATE_DISPATCH_MODE,
        "celery_broker": settings.CELERY_BROKER_URL,
        "celery_backend": settings.CELERY_RESULT_BACKEND,
        "celery_configured": bool(settings.CELERY_BROKER_URL),
    }

    provider_health = get_provider_health_snapshot(now)

    return {
        "debates_24h": debates_24h,
        "debates_7d": debates_7d,
        "active_users_24h": active_users_24h,
        "tokens_24h": tokens_24h,
        "postgres_ok": True,
        "top_models": [{"model_name": model_id, "total_tokens": total} for model_id, total in top_models],
        "rate_limit": {
            "backend": rate_limit_backend,
            "redis_ok": rate_redis_ok,
            "recent_429": recent_429_events[-20:],
            "recent_429_count": len(recent_429_events),
        },
        "sse": {"backend": sse_backend, "redis_ok": sse_redis_ok},
        "models": {"available": bool(models_enabled), "enabled_count": len(models_enabled)},
        "parliament": {
            "seat_counts": dict(seat_counts),
            "model_usage_by_role": model_usage_by_role,
        },
        "provider_health": get_provider_health_snapshot(datetime.now(timezone.utc)),
        "dispatch": dispatch_payload,
        "llm_reliability": {
            "retry_enabled": settings.LLM_RETRY_ENABLED,
            "retry_max_attempts": settings.LLM_RETRY_MAX_ATTEMPTS,
            "debate_max_seat_fail_ratio": settings.DEBATE_MAX_SEAT_FAIL_RATIO,
            "debate_min_required_seats": settings.DEBATE_MIN_REQUIRED_SEATS,
            "debate_fail_fast": settings.DEBATE_FAIL_FAST,
        },
    }


@router.get("/models")
def admin_models(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    enabled_models = list_enabled_models()
    totals: Dict[str, int] = defaultdict(int)
    rows = session.exec(select(BillingUsage)).all()
    for usage in rows:
        for model_id, tokens in (usage.model_tokens or {}).items():
            totals[model_id] += int(tokens or 0)

    default_model = None
    try:
        default_model = get_default_model()
    except Exception:
        default_model = None

    items = []
    for cfg in enabled_models:
        tokens_used = totals.get(cfg.id, 0)
        approx_cost = None
        cost_per_1k = MODEL_COST_PER_1K.get(cfg.id)
        if cost_per_1k is not None:
            approx_cost = round((tokens_used / 1000) * cost_per_1k, 4)
        items.append(
            {
                "id": cfg.id,
                "display_name": cfg.display_name,
                "provider": cfg.provider,
                "is_default": default_model.id == cfg.id if default_model else False,
                "recommended": cfg.recommended,
                "tokens_used": tokens_used,
                "approx_cost_usd": approx_cost,
                "tags": list(cfg.capabilities) if not cfg.tags else cfg.tags,
                "tiers": {
                    "cost": cfg.cost_tier,
                    "latency": cfg.latency_class,
                    "quality": cfg.quality_tier,
                    "safety": cfg.safety_profile,
                },
            }
        )
    return {
        "items": items,
        "default_model": default_model.id if default_model else None,
        "totals": {
            "models": len(enabled_models),
            "tokens_used": sum(totals.values()),
        },
    }


@router.get("/promotions")
def admin_promotions(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    promos = session.exec(select(Promotion).order_by(Promotion.created_at.desc())).all()
    items = [
        {
            "id": str(promo.id),
            "location": promo.location,
            "title": promo.title,
            "target_plan_slug": promo.target_plan_slug,
            "is_active": promo.is_active,
            "priority": promo.priority,
        }
        for promo in promos
    ]
    return {"items": items}


@router.get("/logs")
async def admin_logs(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    rows = session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "id": log.id,
                "action": log.action,
                "user_id": log.user_id,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "meta": log.meta,
                "created_at": log.created_at.isoformat(),
            }
            for log in rows
        ]
    }


@router.get("/events")
def admin_events(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    level: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    query = select(AdminEvent).order_by(AdminEvent.created_at.desc())
    if level:
        query = query.where(AdminEvent.level == level)
    
    # Count total matches
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()
    
    rows = session.exec(query.offset(offset).limit(limit)).all()
    
    return {
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.post("/test-alert")
async def admin_test_alert(
    _: User = Depends(get_current_admin),
):
    from integrations.slack import send_slack_alert
    await send_slack_alert(
        message="Test alert from Admin Console",
        level="info",
        meta={"source": "admin_console", "user": _.email},
        trace_id="test-trace-id",
        mode="test"
    )
    return {"ok": True}


@router.post("/ratings/update/{debate_id}")
async def update_ratings_endpoint(
    debate_id: str,
    _: User = Depends(get_current_admin),
):
    await update_ratings_for_debate(debate_id)
    return {"ok": True}


admin_router = router
