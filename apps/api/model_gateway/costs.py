import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from model_gateway.types import GatewayQuotaExceededError

# Default safety limits
MAX_COST_PER_RUN_USD = 0.50
MAX_MONTHLY_SAFETY_LIMIT_USD = 50.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActiveCostReservation:
    user_id: str
    amount_usd: float


_active_cost_reservation: ContextVar[ActiveCostReservation | None] = ContextVar(
    "active_gateway_cost_reservation",
    default=None,
)


def bind_cost_reservation(user_id: str, amount_usd: float) -> Token:
    """Bind the current call's already-persisted cost reservation.

    The legacy gateway performs its own monthly check after the hardened runtime
    boundary has atomically reserved the conservative full-call estimate. That
    second check must not count the same reservation twice.
    """
    return _active_cost_reservation.set(
        ActiveCostReservation(user_id=user_id, amount_usd=max(float(amount_usd), 0.0))
    )


def reset_cost_reservation(token: Token) -> None:
    _active_cost_reservation.reset(token)


def _month_bounds_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the inclusive UTC month start and exclusive next-month boundary."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    return month_start, next_month


async def check_credit_and_cost_safety(
    user_id: Optional[str],
    user_plan: Optional[str],
    estimated_cost_usd: float = 0.0,
    db_session = None
) -> None:
    """Verify safety limits and user cumulative spend before triggering LLM calls.

    The monthly guard uses the current UTC calendar month and fails closed in
    production/staging when accounting cannot be verified. When the hardened
    gateway runtime has already persisted a conservative reservation for this
    exact call, the reservation amount is subtracted from the aggregate before
    the legacy gateway adds its own estimate, preventing self-double-counting.
    """
    if estimated_cost_usd > MAX_COST_PER_RUN_USD:
        raise GatewayQuotaExceededError(
            f"Estimated run cost (${estimated_cost_usd:.4f}) exceeds the safety cap of ${MAX_COST_PER_RUN_USD:.2f}."
        )

    if db_session and user_id:
        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession

            month_start, next_month = _month_bounds_utc()
            spend_query = text(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage_log "
                "WHERE user_id = :user_id "
                "AND created_at >= :month_start AND created_at < :next_month"
            )
            params = {
                "user_id": user_id,
                "month_start": month_start,
                "next_month": next_month,
            }

            if isinstance(db_session, AsyncSession):
                result = (await db_session.execute(spend_query, params)).scalar()
            else:
                result = db_session.execute(spend_query, params).scalar()

            total_spent = float(result or 0.0)
            reservation = _active_cost_reservation.get()
            if reservation is not None and reservation.user_id == user_id:
                total_spent = max(0.0, total_spent - reservation.amount_usd)

            if total_spent + estimated_cost_usd > MAX_MONTHLY_SAFETY_LIMIT_USD:
                raise GatewayQuotaExceededError(
                    f"User has reached the monthly safety limit of ${MAX_MONTHLY_SAFETY_LIMIT_USD:.2f}."
                )
        except GatewayQuotaExceededError:
            raise
        except Exception as exc:
            from config import settings

            logger.error("Monthly model-cost safety check failed: %s", exc)
            if settings.APP_ENV in {"production", "staging"}:
                raise GatewayQuotaExceededError(
                    "Unable to verify the monthly model-cost safety limit. Please retry shortly."
                ) from exc
            return
