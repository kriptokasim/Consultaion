import asyncio
import logging

from auth import get_current_user
from billing.service import check_export_quota, increment_export_usage
from deps import get_session
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models import Debate, User
from sqlmodel import Session

from routes.common import (
    require_debate_access,
    track_metric,
)
from audit import record_audit

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
    
    # Run heavy export generation in thread pool
    loop = asyncio.get_running_loop()
    content = await loop.run_in_executor(
        None, 
        lambda: report_to_markdown(build_report(session, debate_id, current_user))
    )
    
    # Only increment and commit if export succeeded
    increment_export_usage(session, current_user.id)
    from usage_limits import increment_export_usage_daily
    increment_export_usage_daily(session, current_user.id)
    # FH125 Track G: Record export in usage ledger
    from services.usage_ledger import record_export
    record_export(session, user_id=current_user.id, debate_id=debate_id)
    session.commit()
    
    track_metric("exports_generated")
    record_audit(
        "export_markdown",
        user_id=current_user.id,
        target_type="debate",
        target_id=debate_id,
        session=session,
    )
    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{debate_id}.md"'},
    )
