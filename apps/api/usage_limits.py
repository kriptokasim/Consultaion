from __future__ import annotations

import logging
from datetime import date, timedelta, timezone
from typing import Optional, TypedDict

from database import session_scope
from exceptions import RateLimitError as AppRateLimitError
from models import UsageCounter, UsageQuota, utcnow
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from config import settings


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


class RateLimitError(AppRateLimitError):
    """Quota/rate-limit error compatible with the canonical HTTP error type.

    Older quota code exposed ``detail`` and ``reset_at`` attributes that several
    callers still use for structured 429 payloads. Subclass the application-wide
    RateLimitError so those callers can catch one canonical hierarchy without
    breaking the legacy diagnostic fields.
    """

    def __init__(self, code: str, detail: str, reset_at: str):
        super().__init__(
            message=detail,
            code=code,
            details={"reset_at": reset_at},
        )
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
    try:
        # The unique (user_id, period) index is the concurrency authority.
        # A savepoint lets a losing first-request race recover without rolling
        # back the caller's entire transaction.
        with session.begin_nested():
            session.add(quota)
            session.flush()
        return quota
    except IntegrityError:
        existing = session.exec(
            select(UsageQuota).where(UsageQuota.user_id == user_id, UsageQuota.period == period)
        ).first()
        if existing is None:
            raise
        return existing


def _get_or_reset_counter(session: Session, user_id: str, period: str, *, commit: bool = False, lock: bool = False) -> UsageCounter:
    stmt = select(UsageCounter).where(UsageCounter.user_id == user_id, UsageCounter.period == period)
    if lock:
        stmt = stmt.with_for_update()
    counter = session.exec(stmt).first()
    now = utcnow()
    if not counter:
        counter = UsageCounter(user_id=user_id, period=period, window_start=now)
        try:
            with session.begin_nested():
                session.add(counter)
                session.flush()
        except IntegrityError:
            # Another request initialized the same period while we were
            # selecting. Re-read its committed row and continue from there.
            counter = session.exec(stmt).first()
            if counter is None:
                raise
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
        counter.exports_used = 0
        session.add(counter)
        if commit:
            session.commit()
            session.refresh(counter)
    return counter


def _ensure_daily_token_headroom(session: Session, user_id: str) -> None:
    """Validate run-slot token headroom against canonical plan entitlement.

    ``UsageQuota.max_tokens`` is a legacy global default (150k in current
    config), not a paid-plan entitlement. Using it here silently capped Pro
    users at the global default after the earlier canonical preflight had
    already allowed them. Resolve the same plan-aware daily policy used by
    ``check_quota`` instead.
    """
    from billing.service import get_active_plan
    from plan_config import get_plan_limits

    # Keep the legacy quota row initialized for compatibility/admin tooling, but
    # never use its global max_tokens as the authorization authority.
    _get_or_create_quota(session, user_id, "day")
    counter = _get_or_reset_counter(session, user_id, "day")
    plan = get_active_plan(session, user_id)
    configured_limit = (plan.limits or {}).get("max_tokens_per_day")
    try:
        limit = int(configured_limit) if configured_limit is not None else None
    except (TypeError, ValueError):
        limit = None
    if limit is None:
        limit = get_plan_limits(plan.slug).daily_token_limit

    if limit >= 0 and counter.tokens_used >= limit:
        raise RateLimitError(
            code="tokens_per_day",
            detail="Daily token quota exceeded",
            reset_at=_window_end(counter),
        )


def reserve_run_slot(session: Session, user_id: Optional[str]) -> None:
    """Atomically reserve a run slot and validate token headroom.

    FH125 Track H: Uses conditional UPDATE with FOR UPDATE lock to prevent
    race conditions. Token headroom is checked BEFORE committing.
    """
    if not user_id:
        return

    from models import User
    from security.owner import is_owner
    user = session.get(User, user_id)
    if is_owner(user) and settings.OWNER_UNLIMITED:
        logging.getLogger(__name__).info(
            "owner_override_applied",
            extra={"user_id": user.id, "email": user.email, "override_type": "reserve_run_slot"}
        )
        return

    from models import UsageCounter
    from sqlalchemy import true as sa_true
    quota = _get_or_create_quota(session, user_id, "hour")

    # Atomic: lock row, check limit, increment — all in one statement
    from sqlalchemy import update as sa_update
    if quota.max_runs is None:
        # Unlimited — just increment
        run_limit_clause = sa_true()
    else:
        run_limit_clause = UsageCounter.runs_used < quota.max_runs
    stmt = (
        sa_update(UsageCounter)
        .where(
            UsageCounter.user_id == user_id,
            UsageCounter.period == "hour",
        )
        .where(run_limit_clause)
        .values(runs_used=UsageCounter.runs_used + 1)
        .execution_options(synchronize_session="fetch")
    )
    result = session.execute(stmt)

    if result.rowcount == 0:
        # Row may not exist — create it and retry
        counter = _get_or_reset_counter(session, user_id, "hour", commit=False)
        if quota.max_runs is not None and counter.runs_used >= quota.max_runs:
            raise RateLimitError(
                code="runs_per_hour",
                detail="Hourly run quota exceeded",
                reset_at=_window_end(counter),
            )
        counter.runs_used += 1
        session.add(counter)
    else:
        # Refresh counter to get updated runs_used
        counter = session.exec(
            select(UsageCounter).where(
                UsageCounter.user_id == user_id,
                UsageCounter.period == "hour",
            )
        ).first()

    # Check daily token headroom BEFORE committing
    try:
        _ensure_daily_token_headroom(session, user_id)
    except Exception:
        session.rollback()
        raise

    session.commit()


def _apply_token_usage(session: Session, user_id: str, tokens_int: int, *, commit: bool) -> None:
    quota = _get_or_create_quota(session, user_id, "day")
    _ = quota  # ensure quota exists, even if unused
    counter = _get_or_reset_counter(session, user_id, "day", commit=False, lock=True)
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


def increment_export_usage_daily(session: Session, user_id: str) -> None:
    """Increment the canonical daily export counter without allowing overage.

    The old preflight path compared ``max_exports_per_day`` with the monthly
    ``BillingUsage.exports_count`` counter. Enforce the actual daily window here
    under the same row lock used for the increment, and resolve the limit from
    canonical billing entitlement rather than the legacy ``User.plan`` marker.
    """
    from billing.service import get_active_plan
    from plan_config import get_plan_limits

    counter = _get_or_reset_counter(session, user_id, "day", commit=False, lock=True)
    plan = get_active_plan(session, user_id)
    configured_limit = (plan.limits or {}).get("max_exports_per_day")
    try:
        limit = int(configured_limit) if configured_limit is not None else None
    except (TypeError, ValueError):
        limit = None
    if limit is None:
        limit = get_plan_limits(plan.slug).daily_export_limit

    if limit >= 0 and counter.exports_used >= limit:
        raise AppRateLimitError(
            message="Export quota exceeded. Please try again after the daily window resets or upgrade your plan.",
            code="quota.exports_exceeded",
            details={
                "limit": limit,
                "used": counter.exports_used,
                "window": "daily",
                "reset_at": _window_end(counter),
            },
        )

    counter.exports_used += 1
    session.add(counter)


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
    
    # Get export count from daily counter (FH125 E-5: separate daily/monthly)
    exports_used = counter.exports_used or 0
    
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
    """Check daily token/export quota using canonical billing entitlement.

    ``User.plan`` is a compatibility marker and can be changed by legacy admin
    tooling without changing paid entitlement. Daily quota decisions therefore
    resolve the active BillingSubscription first and only then map its slug to
    the static daily-limit policy.
    """
    # Owner unlimited bypass
    if user is not None:
        from security.owner import is_owner

        from config import settings as _settings
        if is_owner(user) and _settings.OWNER_UNLIMITED:
            import logging
            logging.getLogger(__name__).info(
                "owner_override_applied",
                extra={"user_id": user.id, "email": user.email, "override_type": "quota"},
            )
            return  # bypass all quota checks

    from plan_config import get_plan_limits

    if user is None:
        plan_slug = "free"
    else:
        from billing.service import get_active_plan
        plan_slug = get_active_plan(session, user.id).slug

    limits = get_plan_limits(plan_slug)
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
