import asyncio
import logging

from audit import record_audit
from auth import get_current_user
from billing.service import check_export_quota, increment_export_usage
from deps import get_session
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models import User
from sqlmodel import Session

from routes.common import (
    track_metric,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/debates/{debate_id}/export")
async def export_debate_report(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from services.reporting import build_report, report_to_markdown

    # Check export quota BEFORE doing expensive work (Patchset 65.B1)
    check_export_quota(session, current_user.id)

    # SQLAlchemy/SQLModel sessions are not thread-safe. Keep all DB access on
    # the request thread and offload only the pure report rendering step.
    report = build_report(session, debate_id, current_user)
    loop = asyncio.get_running_loop()
    content = await loop.run_in_executor(None, lambda: report_to_markdown(report))

    # Only increment and commit if export succeeded
    increment_export_usage(session, current_user.id)
    from usage_limits import increment_export_usage_daily
    increment_export_usage_daily(session, current_user.id)
    # FH125 Track G: Record export in usage ledger
    from services.usage_ledger import record_export
    record_export(session, user_id=current_user.id, debate_id=debate_id)
    session.commit()

    track_metric("exports_generated")
    # Usage mutations are already committed. Persist the audit event in its own
    # transaction because the request session does not commit on teardown.
    record_audit(
        "export_markdown",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
    )
    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{debate_id}.md"'},
    )
