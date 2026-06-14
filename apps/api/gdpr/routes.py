"""GDPR API routes.

Provides endpoints for user data export and deletion requests.
Protected by authentication; users can only access their own data.
"""

from __future__ import annotations

import logging
import os
import json
from datetime import datetime, timezone

from auth import get_current_user
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from models import User
from pydantic import BaseModel
from sqlmodel import Session

from .service import (
    create_deletion_request,
    cancel_deletion_request,
    export_user_data,
    process_scheduled_deletions,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


class DeletionRequestResponse(BaseModel):
    status: str
    requested_at: str | None = None
    scheduled_deletion_at: str | None = None
    grace_days: int | None = None
    message: str


@router.post("/export")
def request_data_export(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Export all user data as JSON (GDPR Right of Access)."""
    try:
        export = export_user_data(session, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    # In production, this would queue an async job and return a download URL.
    # For now, write to exports directory and return the file path.
    export_dir = os.path.join(settings.EXPORT_DIR, "gdpr")
    os.makedirs(export_dir, exist_ok=True)
    filename = f"export-{current_user.id[:8]}-{export['export_id'][:8]}.json"
    filepath = os.path.join(export_dir, filename)
    with open(filepath, "w") as f:
        json.dump(export, f, indent=2, default=str)

    logger.info("GDPR export created user=%s file=%s", current_user.id, filename)
    return {
        "status": "ready",
        "export_id": export["export_id"],
        "file": filename,
        "download_url": f"/gdpr/export/download/{filename}",
        "expires_at": (datetime.now(timezone.utc) + __import__("datetime").timedelta(days=7)).isoformat(),
    }


@router.get("/export/download/{filename}")
def download_export(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """Download an exported data file."""
    from fastapi.responses import FileResponse

    export_dir = os.path.join(settings.EXPORT_DIR, "gdpr")
    filepath = os.path.join(export_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    # Security: ensure the filename contains the user's ID prefix
    if not filename.startswith(f"export-{current_user.id[:8]}"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return FileResponse(filepath, media_type="application/json", filename=filename)


@router.post("/deletion-request", response_model=DeletionRequestResponse)
def request_account_deletion(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Request account deletion with 30-day grace period (GDPR Right to Erasure)."""
    result = create_deletion_request(session, current_user.id)
    return DeletionRequestResponse(**result)


@router.post("/deletion-cancel", response_model=DeletionRequestResponse)
def cancel_account_deletion(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending deletion request."""
    result = cancel_deletion_request(session, current_user.id)
    return DeletionRequestResponse(**result)


@router.get("/deletion-status")
def get_deletion_status(
    current_user: User = Depends(get_current_user),
):
    """Check the status of a deletion request."""
    deletion_requested = getattr(current_user, "deletion_requested_at", None)
    if not deletion_requested:
        return {"status": "none", "message": "No deletion request pending."}

    from datetime import timedelta
    grace = timedelta(days=30)
    scheduled = deletion_requested + grace
    now = datetime.now(timezone.utc)

    if scheduled <= now:
        return {"status": "scheduled", "scheduled_deletion_at": scheduled.isoformat()}

    return {
        "status": "pending",
        "requested_at": deletion_requested.isoformat(),
        "scheduled_deletion_at": scheduled.isoformat(),
        "days_remaining": (scheduled - now).days,
    }


# Admin endpoint for processing scheduled deletions
@router.post("/admin/process-deletions")
def admin_process_deletions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Process scheduled deletions (admin only)."""
    from security.owner import is_owner
    if not is_owner(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    count = process_scheduled_deletions(session)
    return {"processed": count, "message": f"Processed {count} scheduled deletions."}


gdpr_router = router
