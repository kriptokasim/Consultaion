from typing import Optional
from model_gateway.types import GatewayQuotaExceededError

# Default safety limits
MAX_COST_PER_RUN_USD = 0.50
MAX_MONTHLY_SAFETY_LIMIT_USD = 50.0

def check_credit_and_cost_safety(
    user_id: Optional[str],
    user_plan: Optional[str],
    estimated_cost_usd: float = 0.0,
    db_session = None
) -> None:
    """Verify safety limits and user credit status before triggering LLM calls."""
    if estimated_cost_usd > MAX_COST_PER_RUN_USD:
        raise GatewayQuotaExceededError(
            f"Estimated run cost (${estimated_cost_usd:.4f}) exceeds the safety cap of ${MAX_COST_PER_RUN_USD:.2f}."
        )
    
    # Optional DB-based checks if a session is active
    if db_session and user_id:
        try:
            from sqlalchemy import text
            result = db_session.execute(
                text("SELECT SUM(cost_usd) FROM llm_usage_log WHERE user_id = :user_id"),
                {"user_id": user_id}
            ).scalar()
            total_spent = float(result or 0.0)
            if total_spent + estimated_cost_usd > MAX_MONTHLY_SAFETY_LIMIT_USD:
                raise GatewayQuotaExceededError(
                    f"User has reached the monthly safety limit of ${MAX_MONTHLY_SAFETY_LIMIT_USD:.2f}."
                )
        except GatewayQuotaExceededError:
            raise
        except Exception:
            # If the database tables aren't fully ready or other error, let it pass to avoid blocking service
            pass
