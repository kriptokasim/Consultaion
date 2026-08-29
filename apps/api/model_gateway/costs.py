import logging
from datetime import datetime, timezone
from typing import Optional

from model_gateway.types import GatewayQuotaExceededError

# Default safety limits
MAX_COST_PER_RUN_USD = 0.50
MAX_MONTHLY_SAFETY_LIMIT_USD = 50.0

logger = logging.getLogger(__name__)


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
    """Verify safety limits and user credit status before triggering LLM calls.

    The monthly guard is evaluated against the current UTC calendar month, not
    lifetime spend. In production/staging it fails closed when accounting
    cannot be verified; allowing paid provider work while the cost ledger is
    unreadable defeats the purpose of the safety cap.

    Sync SQLAlchemy/SQLModel Sessions are intentionally executed on the current
    thread. Sessions are not thread-safe; handing a request-owned Session to a
    generic executor can race its transaction/connection state. The query is a
    single indexed aggregate and is preferable to cross-thread Session use.
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
