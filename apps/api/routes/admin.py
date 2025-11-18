from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from deps import get_session, require_admin
from models import AuditLog, Debate, User
from ratings import update_ratings_for_debate
from routes.common import serialize_team

router = APIRouter(tags=["admin"])


@router.get("/admin/users")
async def admin_users(
    session: Session = Depends(get_session),
    _: Any = Depends(require_admin),
):
    query = (
        select(
            User,
            func.count(Debate.id).label("debate_count"),
            func.max(Debate.created_at).label("last_activity"),
        )
        .outerjoin(Debate, Debate.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )
    rows = session.exec(query).all()
    items: list[dict[str, Any]] = []
    for user, debate_count, last_activity in rows:
        items.append(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "debate_count": int(debate_count or 0),
                "last_activity": last_activity.isoformat() if last_activity else None,
                "created_at": user.created_at.isoformat(),
            }
        )
    return {"items": items}


@router.get("/admin/logs")
async def admin_logs(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: Any = Depends(require_admin),
):
    rows = session.exec(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": log.id,
                "action": log.action,
                "user_id": log.user_id,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "meta": log.meta,
                "created_at": log.created_at.isoformat(),
            }
            for log in rows
        ]
    }


@router.post("/ratings/update/{debate_id}")
async def update_ratings_endpoint(
    debate_id: str,
    _: Any = Depends(require_admin),
):
    await update_ratings_for_debate(debate_id)
    return {"ok": True}


admin_router = router
