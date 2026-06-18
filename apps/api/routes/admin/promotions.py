from __future__ import annotations

from auth import get_current_admin
from deps import get_session
from fastapi import APIRouter, Depends
from models import User
from promotions.models import Promotion
from sqlmodel import Session, select

router = APIRouter()


@router.get("/promotions")
def admin_promotions(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    promos = session.exec(select(Promotion).order_by(Promotion.created_at.desc())).all()
    items = [
        {
            "id": str(promo.id),
            "location": promo.location,
            "title": promo.title,
            "target_plan_slug": promo.target_plan_slug,
            "is_active": promo.is_active,
            "priority": promo.priority,
        }
        for promo in promos
    ]
    return {"items": items}
