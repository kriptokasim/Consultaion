from __future__ import annotations

from auth import get_current_admin
from deps import get_session
from fastapi import APIRouter, Depends
from models import User
from sqlmodel import Session

router = APIRouter()


@router.post("/test-alert")
async def admin_test_alert(
    _: User = Depends(get_current_admin),
):
    from integrations.slack import send_slack_alert
    await send_slack_alert(
        message="Test alert from Admin Console",
        level="info",
        meta={"source": "admin_console", "user": _.email},
        trace_id="test-trace-id",
        mode="test"
    )
    return {"ok": True}


@router.post("/ratings/update/{debate_id}")
async def update_ratings_endpoint(
    debate_id: str,
    _: User = Depends(get_current_admin),
):
    from ratings import update_ratings_for_debate
    await update_ratings_for_debate(debate_id)
    return {"ok": True}
