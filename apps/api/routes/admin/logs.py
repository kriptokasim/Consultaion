from __future__ import annotations

from typing import Optional

from auth import get_current_admin
from deps import get_session
from fastapi import APIRouter, Depends, Query
from models import AdminEvent, AuditLog, User
from sqlalchemy import func
from sqlmodel import Session, select

router = APIRouter()


@router.get("/logs")
async def admin_logs(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    rows = session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
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


@router.get("/events")
def admin_events(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    level: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    query = select(AdminEvent).order_by(AdminEvent.created_at.desc())
    if level:
        query = query.where(AdminEvent.level == level)
    
    # Count total matches
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()
    
    rows = session.exec(query.offset(offset).limit(limit)).all()
    
    return {
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset
    }
