from __future__ import annotations

from datetime import timedelta, timezone
from typing import Optional
import os

from sqlmodel import Session, select

from config import settings
from database import session_scope
from models import UsageCounter, UsageQuota, utcnow


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
