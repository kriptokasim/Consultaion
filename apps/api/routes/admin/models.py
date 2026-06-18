from __future__ import annotations

from collections import defaultdict

from auth import get_current_admin
from billing.models import BillingUsage
from billing.routes import MODEL_COST_PER_1K
from deps import get_session
from fastapi import APIRouter, Depends
from parliament.model_registry import get_default_model, list_enabled_models
from models import User
from sqlmodel import Session, select

router = APIRouter()


@router.get("/models")
def admin_models(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    enabled_models = list_enabled_models()
    totals: dict[str, int] = defaultdict(int)
    rows = session.exec(select(BillingUsage)).all()
    for usage in rows:
        for model_id, tokens in (usage.model_tokens or {}).items():
            totals[model_id] += int(tokens or 0)

    default_model = None
    try:
        default_model = get_default_model()
    except Exception:
        default_model = None

    items = []
    for cfg in enabled_models:
        tokens_used = totals.get(cfg.id, 0)
        approx_cost = None
        cost_per_1k = MODEL_COST_PER_1K.get(cfg.id)
        if cost_per_1k is not None:
            approx_cost = round((tokens_used / 1000) * cost_per_1k, 4)
        items.append(
            {
                "id": cfg.id,
                "display_name": cfg.display_name,
                "provider": cfg.provider,
                "is_default": default_model.id == cfg.id if default_model else False,
                "recommended": cfg.recommended,
                "tokens_used": tokens_used,
                "approx_cost_usd": approx_cost,
                "tags": list(cfg.capabilities) if not cfg.tags else cfg.tags,
                "tiers": {
                    "cost": cfg.cost_tier,
                    "latency": cfg.latency_class,
                    "quality": cfg.quality_tier,
                    "safety": cfg.safety_profile,
                },
            }
        )
    return {
        "items": items,
        "default_model": default_model.id if default_model else None,
        "totals": {
            "models": len(enabled_models),
            "tokens_used": sum(totals.values()),
        },
    }
