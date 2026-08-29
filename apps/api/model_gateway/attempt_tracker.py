"""Per-route provider-attempt accounting for Model Gateway.

A gateway invocation may call more than one adapter (direct model alternatives,
then OpenRouter fallback). The route historically returned only the final
adapter's usage, dropping earlier failed attempts. This tracker runs around each
adapter boundary, extends the user's conservative reservation before every
additional provider attempt, and aggregates all attempt usage into the final
GatewayModelCallResult.

If a failed attempt returns no measurable usage, its conservative reservation
slice is retained rather than silently assuming zero spend.
"""

from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from typing import Any

from model_gateway.reservations import GatewayBudgetReservation
from model_gateway.types import GatewayModelCallResult, GatewayQuotaExceededError

logger = logging.getLogger(__name__)


@dataclass
class AttemptRecord:
    reserved_cost_usd: float
    reserved_tokens: int
    result: GatewayModelCallResult | None = None
    raised: bool = False


@dataclass
class GatewayAttemptContext:
    user_id: str | None
    debate_id: str | None
    user_plan: str | None
    role: str | None
    initial_cost_usd: float
    initial_tokens: int
    reservation: GatewayBudgetReservation | None = None
    records: list[AttemptRecord] = field(default_factory=list)


_current_attempt_context: ContextVar[GatewayAttemptContext | None] = ContextVar(
    "gateway_attempt_context",
    default=None,
)


def bind_attempt_context(context: GatewayAttemptContext) -> Token:
    return _current_attempt_context.set(context)


def reset_attempt_context(token: Token) -> None:
    _current_attempt_context.reset(token)


def get_attempt_context() -> GatewayAttemptContext | None:
    return _current_attempt_context.get()


def _extend_reservation_sync(
    reservation: GatewayBudgetReservation,
    *,
    additional_cost_usd: float,
    additional_tokens: int,
) -> GatewayBudgetReservation:
    """Atomically extend an existing reservation before another adapter call."""
    from database import session_scope
    from model_gateway.costs import MAX_MONTHLY_SAFETY_LIMIT_USD, _month_bounds_utc
    from models import LLMUsageLog, UsageCounter, UsageLedgerEntry, User
    from sqlalchemy import func
    from sqlmodel import select
    from usage_limits import QuotaExceededError, check_quota, record_token_usage

    extra_cost = max(float(additional_cost_usd or 0.0), 0.0)
    extra_tokens = max(int(additional_tokens or 0), 0)

    with session_scope() as session:
        user = session.exec(
            select(User).where(User.id == reservation.user_id).with_for_update()
        ).first()
        if user is None:
            raise GatewayQuotaExceededError("Unable to verify user usage limits.")

        month_start, next_month = _month_bounds_utc()
        current_spend = session.exec(
            select(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0)).where(
                LLMUsageLog.user_id == reservation.user_id,
                LLMUsageLog.created_at >= month_start,
                LLMUsageLog.created_at < next_month,
            )
        ).one()
        if float(current_spend or 0.0) + extra_cost > MAX_MONTHLY_SAFETY_LIMIT_USD:
            raise GatewayQuotaExceededError(
                f"User has reached the monthly safety limit of ${MAX_MONTHLY_SAFETY_LIMIT_USD:.2f}."
            )

        if extra_tokens > 0:
            try:
                check_quota(session, user, required_tokens=extra_tokens)
            except QuotaExceededError as exc:
                raise GatewayQuotaExceededError(
                    f"Daily token quota would be exceeded ({exc.used}/{exc.limit})."
                ) from exc

        usage_log = session.get(LLMUsageLog, reservation.usage_log_id)
        if usage_log is None:
            raise RuntimeError("Gateway reservation disappeared before fallback extension")
        usage_log.cost_usd = max(float(usage_log.cost_usd or 0.0), 0.0) + extra_cost
        usage_log.estimated_cost_usd = max(
            float(usage_log.estimated_cost_usd or 0.0),
            0.0,
        ) + extra_cost
        session.add(usage_log)

        if extra_tokens > 0 and reservation.token_ledger_id:
            entry = session.exec(
                select(UsageLedgerEntry)
                .where(UsageLedgerEntry.id == reservation.token_ledger_id)
                .with_for_update()
            ).first()
            if entry is None or entry.status != "reserved":
                raise RuntimeError("Gateway token reservation is not extendable")
            entry.amount = max(int(entry.amount or 0), 0) + extra_tokens
            meta = dict(entry.meta or {})
            meta["reserved_tokens"] = entry.amount
            meta["provider_attempts_reserved"] = int(
                meta.get("provider_attempts_reserved", 1) or 1
            ) + 1
            entry.meta = meta
            session.add(entry)
            record_token_usage(
                session,
                reservation.user_id,
                extra_tokens,
                commit=False,
            )

        session.commit()
        return replace(
            reservation,
            reserved_cost_usd=reservation.reserved_cost_usd + extra_cost,
            reserved_tokens=reservation.reserved_tokens + extra_tokens,
        )


async def begin_adapter_attempt(
    *,
    messages: list[dict[str, Any]],
    model_id: str,
    max_tokens: int,
) -> int | None:
    """Reserve one attempt slice and return its record index."""
    context = get_attempt_context()
    if context is None:
        return None

    from model_gateway.runtime_guard import (
        estimate_full_call_cost,
        estimate_full_call_tokens,
    )

    if not context.records:
        cost = context.initial_cost_usd
        tokens = context.initial_tokens
    else:
        cost = estimate_full_call_cost(
            messages=messages,
            model_id=model_id,
            max_tokens=max_tokens,
        )
        tokens = estimate_full_call_tokens(
            messages=messages,
            model_id=model_id,
            max_tokens=max_tokens,
        )
        if context.reservation is not None:
            context.reservation = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: _extend_reservation_sync(
                    context.reservation,
                    additional_cost_usd=cost,
                    additional_tokens=tokens,
                ),
            )

    context.records.append(
        AttemptRecord(
            reserved_cost_usd=max(float(cost or 0.0), 0.0),
            reserved_tokens=max(int(tokens or 0), 0),
        )
    )
    return len(context.records) - 1


def finish_adapter_attempt(
    index: int | None,
    *,
    result: GatewayModelCallResult | None = None,
    raised: bool = False,
) -> None:
    context = get_attempt_context()
    if context is None or index is None or index >= len(context.records):
        return
    record = context.records[index]
    record.result = result
    record.raised = raised


def aggregate_accounting_result(
    final_result: GatewayModelCallResult,
    context: GatewayAttemptContext,
) -> GatewayModelCallResult:
    """Return final user content with usage aggregated across provider attempts."""
    if not context.records:
        return final_result

    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    cost_usd = 0.0
    estimated_cost = 0.0

    for record in context.records:
        result = record.result
        measurable = bool(
            result is not None
            and (
                result.success
                or int(result.total_tokens or 0) > 0
                or float(result.cost_usd or 0.0) > 0
            )
        )
        if measurable and result is not None:
            prompt_tokens += max(int(result.prompt_tokens or 0), 0)
            completion_tokens += max(int(result.completion_tokens or 0), 0)
            total_tokens += max(
                int(result.total_tokens or 0),
                int(result.prompt_tokens or 0) + int(result.completion_tokens or 0),
            )
            cost_usd += max(float(result.cost_usd or 0.0), 0.0)
            estimated_cost += max(float(result.estimated_cost_usd or 0.0), 0.0)
        else:
            # Provider execution may have happened even when its SDK returned no
            # usage object. Preserve the pre-provider reservation for this
            # uncertain failed attempt instead of undercounting it as zero.
            total_tokens += record.reserved_tokens
            cost_usd += record.reserved_cost_usd
            estimated_cost += record.reserved_cost_usd

    final_result.prompt_tokens = prompt_tokens
    final_result.completion_tokens = completion_tokens
    final_result.total_tokens = max(total_tokens, prompt_tokens + completion_tokens)
    final_result.cost_usd = max(cost_usd, 0.0)
    final_result.estimated_cost_usd = max(
        estimated_cost,
        context.reservation.reserved_cost_usd if context.reservation else context.initial_cost_usd,
    )
    final_result.retry_count = max(
        int(final_result.retry_count or 0),
        max(len(context.records) - 1, 0),
    )
    return final_result
