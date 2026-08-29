"""Atomic per-user reservations for model-gateway provider calls.

Parallel Arena fan-out means a check-then-call cost/token policy is racy: every
model can observe the same remaining monthly/daily headroom before any result is
persisted. These helpers serialize reservations on the User row, charge a
conservative full-call estimate before provider work, then settle to actual
usage in the same durable identities.

A worker crash after reservation but before settlement intentionally leaves the
conservative estimate charged. That is fail-closed: it may over-account one
uncertain call, but cannot silently overspend or bypass the daily quota.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from model_gateway.types import GatewayModelCallResult, GatewayQuotaExceededError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatewayBudgetReservation:
    usage_log_id: str
    token_ledger_id: str | None
    user_id: str
    reserved_cost_usd: float
    reserved_tokens: int


def _resolve_attempt_id(session, debate_id: str | None) -> str | None:
    if not debate_id:
        return None

    from models import Debate, DebateAttempt
    from orchestration.execution_context import get_current_execution_lease
    from sqlmodel import select

    lease = get_current_execution_lease()
    attempt_number: int | None = None
    if lease is not None and lease.debate_id == debate_id:
        attempt_number = max(int(lease.run_attempt or 0), 1)
    else:
        debate = session.get(Debate, debate_id)
        if debate is not None:
            attempt_number = max(int(debate.run_attempt or 0), 1)

    if attempt_number is None:
        return None
    attempt = session.exec(
        select(DebateAttempt).where(
            DebateAttempt.debate_id == debate_id,
            DebateAttempt.attempt_number == attempt_number,
        )
    ).first()
    return attempt.id if attempt is not None else None


def reserve_gateway_budget_sync(
    *,
    user_id: str,
    debate_id: str | None,
    model_id: str,
    role: str | None,
    user_plan: str | None,
    estimated_cost_usd: float,
    estimated_tokens: int,
) -> GatewayBudgetReservation:
    """Atomically reserve monthly dollars and daily tokens for one call."""
    from database import session_scope
    from model_gateway.costs import (
        MAX_COST_PER_RUN_USD,
        MAX_MONTHLY_SAFETY_LIMIT_USD,
        _month_bounds_utc,
    )
    from models import LLMUsageLog, UsageLedgerEntry, User
    from sqlalchemy import func
    from sqlmodel import select
    from usage_limits import QuotaExceededError, check_quota, record_token_usage

    cost = max(float(estimated_cost_usd or 0.0), 0.0)
    tokens = max(int(estimated_tokens or 0), 0)
    if cost > MAX_COST_PER_RUN_USD:
        raise GatewayQuotaExceededError(
            f"Estimated run cost (${cost:.4f}) exceeds the safety cap of ${MAX_COST_PER_RUN_USD:.2f}."
        )

    with session_scope() as session:
        # Serialize all cost/token reservations for this user. PostgreSQL honors
        # FOR UPDATE; SQLite test runs are serialized by its writer lock.
        user = session.exec(
            select(User).where(User.id == user_id).with_for_update()
        ).first()
        if user is None:
            raise GatewayQuotaExceededError("Unable to verify user usage limits.")

        month_start, next_month = _month_bounds_utc()
        current_spend = session.exec(
            select(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0)).where(
                LLMUsageLog.user_id == user_id,
                LLMUsageLog.created_at >= month_start,
                LLMUsageLog.created_at < next_month,
            )
        ).one()
        current_spend_value = float(current_spend or 0.0)
        if current_spend_value + cost > MAX_MONTHLY_SAFETY_LIMIT_USD:
            raise GatewayQuotaExceededError(
                f"User has reached the monthly safety limit of ${MAX_MONTHLY_SAFETY_LIMIT_USD:.2f}."
            )

        if tokens > 0:
            try:
                check_quota(session, user, required_tokens=tokens)
            except QuotaExceededError as exc:
                raise GatewayQuotaExceededError(
                    f"Daily token quota would be exceeded ({exc.used}/{exc.limit})."
                ) from exc

        reservation_log = LLMUsageLog(
            debate_id=debate_id,
            user_id=user_id,
            provider="reservation",
            model=model_id,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=cost,
            gateway="runtime_guard",
            model_pool=None,
            routing_policy="preflight_reservation",
            fallback_used=False,
            fallback_reason=None,
            user_plan=user_plan,
            estimated_cost_usd=cost,
            retry_count=0,
            role=role,
            latency_ms=0.0,
            success=False,
            error_message=None,
        )
        session.add(reservation_log)
        session.flush()

        attempt_id = _resolve_attempt_id(session, debate_id)
        token_ledger_id: str | None = None
        if tokens > 0:
            token_entry = UsageLedgerEntry(
                user_id=user_id,
                kind="gateway_token_usage",
                status="reserved",
                idempotency_key=f"gateway_token:{reservation_log.id}",
                amount=tokens,
                debate_id=debate_id,
                attempt_id=attempt_id,
                meta={
                    "llm_usage_log_id": reservation_log.id,
                    "reserved_tokens": tokens,
                    "model": model_id,
                },
            )
            session.add(token_entry)
            record_token_usage(
                session,
                user_id,
                tokens,
                commit=False,
            )
            session.flush()
            token_ledger_id = token_entry.id

        session.commit()
        return GatewayBudgetReservation(
            usage_log_id=reservation_log.id,
            token_ledger_id=token_ledger_id,
            user_id=user_id,
            reserved_cost_usd=cost,
            reserved_tokens=tokens,
        )


def _adjust_reserved_tokens(
    session,
    reservation: GatewayBudgetReservation,
    actual_tokens: int,
) -> None:
    """Set daily token reservation to actual usage without double-counting."""
    from models import UsageCounter, UsageLedgerEntry
    from sqlmodel import select
    from usage_limits import record_token_usage

    actual = max(int(actual_tokens or 0), 0)
    entry = (
        session.exec(
            select(UsageLedgerEntry)
            .where(UsageLedgerEntry.id == reservation.token_ledger_id)
            .with_for_update()
        ).first()
        if reservation.token_ledger_id
        else None
    )
    if entry is None:
        if actual > 0:
            # Reservation metadata disappeared after provider work. Preserve
            # quota correctness rather than silently dropping actual usage.
            record_token_usage(session, reservation.user_id, actual, commit=False)
        return

    reserved = max(int(entry.amount or 0), 0)
    delta = actual - reserved
    if delta > 0:
        # This should be rare because reservation includes max output tokens,
        # but real provider accounting remains authoritative after the call.
        record_token_usage(session, reservation.user_id, delta, commit=False)
        logger.error(
            "gateway.token_reservation_underestimated reservation=%s reserved=%s actual=%s",
            reservation.usage_log_id,
            reserved,
            actual,
        )
    elif delta < 0:
        counter = session.exec(
            select(UsageCounter)
            .where(
                UsageCounter.user_id == reservation.user_id,
                UsageCounter.period == "day",
            )
            .with_for_update()
        ).first()
        if counter is not None:
            counter.tokens_used = max(0, int(counter.tokens_used or 0) + delta)
            session.add(counter)

    meta = dict(entry.meta or {})
    meta.update(
        {
            "reserved_tokens": reserved,
            "actual_tokens": actual,
            "settled": True,
        }
    )
    entry.amount = actual
    entry.status = "settled"
    entry.meta = meta
    session.add(entry)


def settle_gateway_budget_sync(
    reservation: GatewayBudgetReservation,
    *,
    result: GatewayModelCallResult,
    safe_error_message: str | None,
) -> None:
    """Replace conservative reservation with actual provider result."""
    from database import session_scope
    from models import LLMUsageLog, User
    from sqlmodel import select

    with session_scope() as session:
        # Serialize settlement against a concurrent new reservation for user.
        session.exec(
            select(User).where(User.id == reservation.user_id).with_for_update()
        ).first()
        usage_log = session.get(LLMUsageLog, reservation.usage_log_id)
        if usage_log is None:
            raise RuntimeError("Gateway cost reservation disappeared before settlement")

        actual_tokens = max(int(result.total_tokens or 0), 0)
        _adjust_reserved_tokens(session, reservation, actual_tokens)

        usage_log.provider = result.provider or "unknown"
        usage_log.model = result.model_used or usage_log.model
        usage_log.prompt_tokens = max(int(result.prompt_tokens or 0), 0)
        usage_log.completion_tokens = max(int(result.completion_tokens or 0), 0)
        usage_log.total_tokens = actual_tokens
        usage_log.cost_usd = max(float(result.cost_usd or 0.0), 0.0)
        usage_log.gateway = result.gateway
        usage_log.model_pool = result.model_pool
        usage_log.routing_policy = result.routing_policy
        usage_log.fallback_used = bool(result.fallback_used)
        usage_log.fallback_reason = (result.fallback_reason or "")[:500] or None
        usage_log.user_plan = result.user_plan or usage_log.user_plan
        usage_log.estimated_cost_usd = max(
            float(result.estimated_cost_usd or 0.0),
            reservation.reserved_cost_usd,
        )
        usage_log.retry_count = max(int(result.retry_count or 0), 0)
        usage_log.latency_ms = max(float(result.latency_ms or 0.0), 0.0)
        usage_log.success = bool(result.success)
        usage_log.error_message = safe_error_message
        session.add(usage_log)
        session.commit()


def release_gateway_budget_sync(
    reservation: GatewayBudgetReservation,
    *,
    reason: str,
) -> None:
    """Release a reservation known to have failed before provider execution."""
    from database import session_scope
    from models import LLMUsageLog, UsageCounter, UsageLedgerEntry, User
    from sqlmodel import select

    with session_scope() as session:
        session.exec(
            select(User).where(User.id == reservation.user_id).with_for_update()
        ).first()
        usage_log = session.get(LLMUsageLog, reservation.usage_log_id)
        if usage_log is not None:
            usage_log.cost_usd = 0.0
            usage_log.provider = "reservation_released"
            usage_log.routing_policy = "preflight_released"
            usage_log.success = False
            usage_log.error_message = reason[:500]
            session.add(usage_log)

        if reservation.token_ledger_id:
            entry = session.exec(
                select(UsageLedgerEntry)
                .where(UsageLedgerEntry.id == reservation.token_ledger_id)
                .with_for_update()
            ).first()
            if entry is not None and entry.status == "reserved":
                counter = session.exec(
                    select(UsageCounter)
                    .where(
                        UsageCounter.user_id == reservation.user_id,
                        UsageCounter.period == "day",
                    )
                    .with_for_update()
                ).first()
                if counter is not None:
                    counter.tokens_used = max(
                        0,
                        int(counter.tokens_used or 0) - max(int(entry.amount or 0), 0),
                    )
                    session.add(counter)
                entry.status = "refunded"
                meta = dict(entry.meta or {})
                meta.update({"released_before_provider": True, "reason": reason[:200]})
                entry.meta = meta
                session.add(entry)
        session.commit()
