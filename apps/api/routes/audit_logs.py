import csv
import io
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select, desc

from auth import get_current_user
from deps import get_session
from models import User, UserInteraction

router = APIRouter(prefix="/audit-logs", tags=["audit_logs"])


class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    debate_id: str | None
    interaction_type: str
    details: dict | None
    created_at: datetime


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Retrieve audit logs (User Interactions) for the current user."""
    stmt = (
        select(UserInteraction)
        .where(UserInteraction.user_id == current_user.id)
        .order_by(desc(UserInteraction.created_at))
        .limit(100)
    )
    logs = session.exec(stmt).all()
    return logs


@router.get("/export/csv")
async def export_audit_logs_csv(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Export audit logs as a CSV stream."""
    stmt = (
        select(UserInteraction)
        .where(UserInteraction.user_id == current_user.id)
        .order_by(desc(UserInteraction.created_at))
    )
    logs = session.exec(stmt).all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow(["ID", "Timestamp", "Event Type", "Debate ID", "Details JSON"])
    
    for log in logs:
        writer.writerow([
            log.id,
            log.created_at.isoformat(),
            log.interaction_type,
            log.debate_id or "",
            json.dumps(log.details) if log.details else ""
        ])

    output.seek(0)
    
    # Set filename
    headers = {
        'Content-Disposition': f'attachment; filename="consultaion_audit_logs_{current_user.id[:8]}.csv"'
    }
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers=headers
    )


@router.get("/export/json")
async def export_audit_logs_json(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Export audit logs as a downloadable JSON file."""
    stmt = (
        select(UserInteraction)
        .where(UserInteraction.user_id == current_user.id)
        .order_by(desc(UserInteraction.created_at))
    )
    logs = session.exec(stmt).all()

    data = [
        {
            "id": log.id,
            "created_at": log.created_at.isoformat(),
            "interaction_type": log.interaction_type,
            "debate_id": log.debate_id,
            "details": log.details
        }
        for log in logs
    ]

    content = json.dumps(data, indent=2)
    headers = {
        'Content-Disposition': f'attachment; filename="consultaion_audit_logs_{current_user.id[:8]}.json"'
    }
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers=headers
    )
