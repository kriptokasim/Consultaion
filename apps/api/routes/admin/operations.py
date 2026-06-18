from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from auth import get_current_admin
from billing.models import BillingUsage
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, Request
from models import Debate, User
from parliament.model_registry import list_enabled_models
from parliament.provider_health import get_provider_health_snapshot
from ratelimit import ensure_rate_limiter_ready, get_recent_429_events
from sqlalchemy import func
from sqlmodel import Session, select
from sse_backend import get_sse_backend

router = APIRouter()


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


@router.post("/maintenance/purge")
def admin_purge_old_data(
    req: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Trigger data retention purge jobs.
    
    Anonymizes/deletes old data according to RETAIN_*_DAYS settings.
    Intended to be called by cron job or manually.
    """
    from audit import record_audit
    from maintenance.retention import run_all_purges
    
    results = run_all_purges(session)
    
    record_audit(
        "maintenance_purge",
        user_id=admin.id,
        target_type="system",
        target_id=None,
        meta=results,
        ip_address=req.client.host if req.client else None,
        session=session,
    )
    
    return {
        "status": "ok",
        "purged": results,
    }
