from __future__ import annotations

from datetime import date, timedelta, timezone
from typing import Optional, TypedDict

from config import settings
from database import session_scope
from models import UsageCounter, UsageQuota, utcnow
from sqlmodel import Session, select


def _default_max_runs_per_hour() -> int:
    return settings.DEFAULT_MAX_RUNS_PER_HOUR


def _default_max_tokens_per_day() -> int:
    return settings.DEFAULT_MAX_TOKENS_PER_DAY


def _period_seconds(period: str) -> int:
    return 3600 if period == "hour" else 86400


def _window_end(counter: UsageCounter) -> str:
    start = counter.window_start
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(seconds=_period_seconds(counter.period))
    return end.isoformat()


class RateLimitError(Exception):
    def __init__(self, code: str, detail: str, reset_at: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.reset_at = reset_at


class QuotaExceededError(Exception):
    """Raised when user exceeds their quota."""
    def __init__(self, kind: str, limit: int, used: int):
        self.kind = kind  # "tokens" or "exports"
        self.limit = limit
        self.used = used
        super().__init__(f"{kind} quota exceeded: {used}/{limit}")


def _get_or_create_quota(session: Session, user_id: str, period: str) -> UsageQuota:
    quota = session.exec(
        select(UsageQuota).where(UsageQuota.user_id == user_id, UsageQuota.period == period)
    ).first()
    if quota:
        return quota

    if period == "hour":
        quota = UsageQuota(
            user_id=user_id,
            period=period,
            max_runs=_default_max_runs_per_hour(),
            max_tokens=None,
            reset_at=utcnow() + timedelta(seconds=_period_seconds(period)),
        )
    else:
        quota = UsageQuota(
            user_id=user_id,
            period=period,
            max_runs=None,
            max_tokens=_default_max_tokens_per_day(),
            reset_at=utcnow() + timedelta(seconds=_period_seconds(period)),
        )
    session.add(quota)
    session.commit()
    session.refresh(quota)
    return quota


def _get_or_reset_counter(session: Session, user_id: str, period: str, *, commit: bool = True) -> UsageCounter:
    counter = session.exec(
        select(UsageCounter).where(UsageCounter.user_id == user_id, UsageCounter.period == period)
    ).first()
    now = utcnow()
    if not counter:
        counter = UsageCounter(user_id=user_id, period=period, window_start=now)
        session.add(counter)
        if commit:
            session.commit()
            session.refresh(counter)
        return counter

    base_time = counter.window_start
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)
    elapsed = (now - base_time).total_seconds()
    if elapsed >= _period_seconds(period):
        counter.window_start = now
        counter.runs_used = 0
        counter.tokens_used = 0
        session.add(counter)
        if commit:
            session.commit()
            session.refresh(counter)
    return counter


def _ensure_daily_token_headroom(session: Session, user_id: str) -> None:
    quota = _get_or_create_quota(session, user_id, "day")
    counter = _get_or_reset_counter(session, user_id, "day")
    if quota.max_tokens is not None and counter.tokens_used >= quota.max_tokens:
        raise RateLimitError(
            code="tokens_per_day",
            detail="Daily token quota exceeded",
            reset_at=_window_end(counter),
        )


def reserve_run_slot(session: Session, user_id: Optional[str]) -> None:
    if not user_id:
        return
    quota = _get_or_create_quota(session, user_id, "hour")
    counter = _get_or_reset_counter(session, user_id, "hour")
    if quota.max_runs is not None and counter.runs_used + 1 > quota.max_runs:
        raise RateLimitError(
            code="runs_per_hour",
            detail="Hourly run quota exceeded",
            reset_at=_window_end(counter),
        )
    counter.runs_used += 1
    session.add(counter)
    session.commit()
    _ensure_daily_token_headroom(session, user_id)


def _apply_token_usage(session: Session, user_id: str, tokens_int: int, *, commit: bool) -> None:
    quota = _get_or_create_quota(session, user_id, "day")
    _ = quota  # ensure quota exists, even if unused
    counter = _get_or_reset_counter(session, user_id, "day", commit=False)
    counter.tokens_used += tokens_int
    session.add(counter)
    if commit:
        session.commit()


def record_token_usage(
    session: Optional[Session],
    user_id: Optional[str],
    tokens_used: float | int,
    *,
    commit: bool = True,
) -> None:
    if not user_id:
        return
    tokens_int = int(max(tokens_used, 0))
    if session is None:
        with session_scope() as scoped:
            _apply_token_usage(scoped, user_id, tokens_int, commit=True)
    else:
        _apply_token_usage(session, user_id, tokens_int, commit=commit)


class DailyUsage(TypedDict):
    """Daily usage statistics for a user."""
    tokens_used: int
    exports_used: int
    date: str  # YYYY-MM-DD


def get_today_usage(session: Session, user_id: Optional[str]) -> DailyUsage:
    """
    Get today's token and export usage for a user.
    
    Args:
        session: Database session
        user_id: User ID (None for anonymous users)
    
    Returns:
        DailyUsage dict with tokens_used, exports_used, and date
    """
    today = date.today().isoformat()
    
    if user_id is None:
        return {"tokens_used": 0, "exports_used": 0, "date": today}
    
    # Get today's token counter
    counter = _get_or_reset_counter(session, user_id, "day", commit=False)
    tokens_used = counter.tokens_used or 0
    
    # Get export count from billing service
    # NOTE: May need to adapt if billing tracks monthly not daily
    try:
        from billing.service import get_billing_usage
        usage = get_billing_usage(session, user_id)
        # For now, use month count as proxy; future: add daily export counter
        exports_used = usage.get("exports_this_month", 0)
    except Exception:
        # Gracefully fall back if billing not available
        exports_used = 0
    
    return {
        "tokens_used": tokens_used,
        "exports_used": exports_used,
        "date": today,
    }


def check_quota(
    session: Session,
    user: Optional["User"],  # noqa: F821
    required_tokens: int = 0,
    required_exports: int = 0,
) -> None:
    """
    Check if user has quota for the requested operation.
    
    Raises QuotaExceededError if user would exceed their daily limits.
    
    Args:
        session: Database session
        user: User object (None for anonymous)
        required_tokens: Estimated tokens needed for operation
        required_exports: Number of exports needed (usually 0 or 1)
    
    Raises:
        QuotaExceededError: If quota would be exceeded
    """
    from plan_config import get_plan_limits, resolve_plan_for_user
    
    plan_name = resolve_plan_for_user(user)
    limits = get_plan_limits(plan_name)
    usage = get_today_usage(session, user.id if user else None)
    
    # Check token quota
    if required_tokens > 0:
        if usage["tokens_used"] + required_tokens > limits.daily_token_limit:
            raise QuotaExceededError(
                "tokens",
                limits.daily_token_limit,
                usage["tokens_used"]
            )
    
    # Check export quota
    if required_exports > 0:
        if usage["exports_used"] + required_exports > limits.daily_export_limit:
            raise QuotaExceededError(
                "exports",
                limits.daily_export_limit,
                usage["exports_used"]
            )
