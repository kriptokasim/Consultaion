from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from auth import get_optional_user
from deps import get_session
from billing.service import get_active_plan
from models import User

from .models import Promotion

router = APIRouter(prefix="/promotions", tags=["promotions"])


@router.get("")
def list_promotions(
    location: str = Query(..., description="Location identifier (e.g., dashboard_sidebar)."),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    stmt = (
        select(Promotion)
        .where(Promotion.location == location, Promotion.is_active.is_(True))
        .order_by(Promotion.priority.asc())
    )
    promos = session.exec(stmt).all()
    if not promos:
        return {"items": []}

    plan_slug: Optional[str] = None
    if current_user:
        plan = get_active_plan(session, current_user.id)
        plan_slug = plan.slug

    items: List[Dict[str, Optional[str]]] = []
    for promo in promos:
        if promo.target_plan_slug and plan_slug and promo.target_plan_slug != plan_slug:
            continue
        if promo.target_plan_slug and plan_slug is None:
            continue
        items.append(
            {
                "id": str(promo.id),
                "title": promo.title,
                "body": promo.body,
                "cta_label": promo.cta_label,
                "cta_url": promo.cta_url,
            }
        )
    return {"items": items}


promotions_router = router
