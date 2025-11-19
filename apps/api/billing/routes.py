from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from deps import get_current_user, get_session
from model_registry import ALL_MODELS
from models import User

from .models import BillingUsage
from .service import _current_period

router = APIRouter(prefix="/billing", tags=["billing"])

MODEL_COST_PER_1K = {
    "router-smart": 0.50,
    "router-deep": 0.75,
    "gpt4o-mini": 0.60,
    "gpt4o-deep": 1.00,
    "claude-sonnet": 1.20,
    "claude-haiku": 0.35,
    "gemini-flash": 0.20,
    "gemini-pro": 0.90,
}


def _resolve_model_meta(model_id: str) -> Dict[str, object]:
    cfg = ALL_MODELS.get(model_id)
    return {
        "model_id": model_id,
        "display_name": cfg.display_name if cfg else model_id,
    }


@router.get("/usage/models")
def get_model_usage(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    period = _current_period()
    stmt = select(BillingUsage).where(BillingUsage.user_id == current_user.id, BillingUsage.period == period)
    usage = session.exec(stmt).first()
    if not usage or not usage.model_tokens:
        return {"items": []}

    items: List[Dict[str, object]] = []
    for model_id, tokens in usage.model_tokens.items():
        meta = _resolve_model_meta(model_id)
        cost_per_1k = MODEL_COST_PER_1K.get(model_id)
        approx_cost = None
        if cost_per_1k is not None:
            approx_cost = round((int(tokens) / 1000) * cost_per_1k, 4)
        items.append(
            {
                **meta,
                "tokens_used": int(tokens),
                "approx_cost_usd": approx_cost,
            }
        )
    return {"items": items}


billing_router = router
