import logging
from typing import Dict, Any
from model_gateway.types import GatewayDecision, GatewayModelCallResult

logger = logging.getLogger("model_gateway.observability")

def log_gateway_decision(decision: GatewayDecision, user_id: str | None = None) -> None:
    """Log gateway routing decisions for analytics."""
    logger.info(
        "gateway_decision",
        extra={
            "selected_model": decision.selected_model,
            "selected_provider": decision.selected_provider,
            "policy_used": decision.policy_used,
            "model_pool": decision.model_pool,
            "user_id": user_id,
        }
    )

def log_gateway_call_metrics(result: GatewayModelCallResult, user_id: str | None = None) -> None:
    """Log latency, cost, and usage metrics of gateway execution."""
    logger.info(
        "gateway_metrics",
        extra={
            "model_used": result.model_used,
            "provider": result.provider,
            "latency_ms": result.latency_ms,
            "cost_usd": result.cost_usd,
            "fallback_used": result.fallback_used,
            "retry_count": result.retry_count,
            "user_id": user_id,
        }
    )
