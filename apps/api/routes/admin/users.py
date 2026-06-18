from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from auth import get_current_admin
from billing.models import BillingPlan, BillingSubscription, BillingUsage
from billing.service import get_active_plan
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from models import Debate, SupportNote, User
from pydantic import BaseModel
from sqlmodel import Session, select

from routes.admin.dependencies import (
    _activity_snapshot,
    _latest_usage,
    _plan_payload,
    _usage_payload,
)
from routes.common import serialize_user

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ChangePlanRequest(BaseModel):
    plan: str


class CreateNoteRequest(BaseModel):
    note: str


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


@router.get("/users")
def admin_users(
    q: Optional[str] = Query(None, description="Search by email/display name."),
    plan_slug: Optional[str] = Query(None, description="Filter users by active plan slug."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    activity = _activity_snapshot(session)
    filtered: List[Dict[str, Any]] = []
    q_lower = q.lower() if q else None

    # Prefetch plans, subscriptions, and usages
    from billing.models import BillingPlan, BillingSubscription, BillingUsage
    from security.owner import is_owner
    from datetime import datetime, timezone

    plans = session.exec(select(BillingPlan)).all()
    plan_map = {p.id: p for p in plans}
    slug_map = {p.slug: p for p in plans}
    default_free_plan = next((p for p in plans if p.is_default_free), None)

    now_dt = datetime.now(timezone.utc)
    user_ids = [u.id for u in users]

    user_sub_map = {}
    if user_ids:
        subscriptions = session.exec(
            select(BillingSubscription)
            .where(
                BillingSubscription.user_id.in_(user_ids),
                BillingSubscription.status == "active",
                BillingSubscription.current_period_end >= now_dt,
            )
            .order_by(BillingSubscription.current_period_end.desc())
        ).all()
        for sub in subscriptions:
            if sub.user_id not in user_sub_map:
                user_sub_map[sub.user_id] = sub

    user_usage_map = {}
    if user_ids:
        usages = session.exec(
            select(BillingUsage)
            .where(BillingUsage.user_id.in_(user_ids))
            .order_by(BillingUsage.period.desc())
        ).all()
        for usage in usages:
            if usage.user_id not in user_usage_map:
                user_usage_map[usage.user_id] = usage

    for user in users:
        if q_lower:
            display = (user.display_name or "").lower()
            email_match = q_lower in user.email.lower()
            display_match = q_lower in display
            if not email_match and not display_match:
                continue

        # Resolve active plan in-memory
        plan = None
        if is_owner(user):
            owner_slug = settings.OWNER_PLAN
            plan = slug_map.get(owner_slug) or default_free_plan
        else:
            sub = user_sub_map.get(user.id)
            if sub:
                plan = plan_map.get(sub.plan_id)
            if not plan:
                plan = default_free_plan

        if plan_slug and (not plan or plan.slug != plan_slug):
            continue

        usage = user_usage_map.get(user.id)
        row = {
            **serialize_user(user),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "plan": _plan_payload(plan),
            "usage": _usage_payload(usage),
        }
        stats = activity.get(user.id, {"debate_count": 0, "last_activity": None})
        row.update(
            {
                "debate_count": stats.get("debate_count", 0),
                "last_activity": stats.get("last_activity"),
            }
        )
        filtered.append(row)
    total = len(filtered)
    items = filtered[offset : offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/users/{user_id}")
def admin_user_detail(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    plan = None
    try:
        plan = get_active_plan(session, user.id)
    except HTTPException:
        plan = None
    usage = _latest_usage(session, user.id)
    subscriptions = session.exec(
        select(BillingSubscription).where(BillingSubscription.user_id == user.id).order_by(BillingSubscription.created_at.desc())
    ).all()
    subs_payload = [
        {
            "id": str(sub.id),
            "plan_id": str(sub.plan_id),
            "status": sub.status,
            "current_period_start": sub.current_period_start.isoformat(),
            "current_period_end": sub.current_period_end.isoformat(),
            "provider": sub.provider,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
        for sub in subscriptions
    ]
    return {
        "user": serialize_user(user),
        "plan": _plan_payload(plan),
        "usage": _usage_payload(usage),
        "subscriptions": subs_payload,
    }


@router.get("/users/{user_id}/billing")
def admin_user_billing(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    plan = None
    try:
        plan = get_active_plan(session, user.id)
    except HTTPException:
        plan = None
    from billing.service import _current_period
    current_period = _current_period()
    usage = session.exec(
        select(BillingUsage).where(BillingUsage.user_id == user.id, BillingUsage.period == current_period)
    ).first()
    return {
        "plan": _plan_payload(plan),
        "usage": _usage_payload(usage),
    }


@router.post("/users/{user_id}/plan")
def change_user_plan(
    user_id: str,
    request: ChangePlanRequest,
    req: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Change a user's subscription plan (admin only).
    
    Validates that the plan exists and logs the change for audit purposes.
    
    Args:
        user_id: ID of user to update
        request: ChangePlanRequest with new plan name
        session: Database session
        admin: Current admin user (auth check)
    
    Returns:
        Updated user info with old and new plan
    
    Raises:
        HTTPException: 400 if plan invalid, 404 if user not found
    """
    import logging

    from plan_config import validate_plan
    
    logger = logging.getLogger(__name__)
    
    # Validate plan exists
    if not validate_plan(request.plan):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan: {request.plan}. Must be one of: free, pro, internal"
        )
    
    # Get user
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_plan = user.plan
    user.plan = request.plan
    session.commit()
    
    # Audit log
    logger.info(
        f"Plan changed by admin {admin.email} ({admin.id}): "
        f"user={user.email} ({user.id}) old_plan={old_plan} new_plan={request.plan}"
    )
    
    from audit import record_audit
    record_audit(
        "plan_changed",
        user_id=admin.id,
        target_type="user",
        target_id=user.id,

        meta={"old_plan": old_plan, "new_plan": request.plan, "target_email": user.email},
        ip_address=req.client.host if req.client else None,
        session=session,
    )
    
    return {
        "user_id": user.id,
        "email": user.email,
        "old_plan": old_plan,
        "new_plan": request.plan,
    }


@router.get("/users")
def admin_search_users(
    email: Optional[str] = Query(None, description="Search by email substring"),
    id: Optional[str] = Query(None, description="Search by exact user ID"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    Search for users by email or ID.
    Returns basic user info for admin listing.
    """
    query = select(User)
    
    if id:
        query = query.where(User.id == id)
    elif email:
        query = query.where(User.email.contains(email))
    
    users = session.exec(query.order_by(User.created_at.desc()).limit(limit)).all()
    
    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "plan": user.plan,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "is_active": user.is_active,
            }
            for user in users
        ],
        "total": len(users),
    }


@router.get("/users/{user_id}/summary")
def admin_user_summary(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    Get comprehensive user summary including quota, recent debates, and feedback.
    """
    from plan_config import get_plan_limits
    from usage_limits import get_today_usage
    
    # Get user
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get quota usage
    usage = get_today_usage(session, user_id)
    limits = get_plan_limits(user.plan)
    
    # Get recent debates
    recent_debates = session.exec(
        select(Debate)
        .where(Debate.user_id == user_id)
        .order_by(Debate.created_at.desc())
        .limit(10)
    ).all()
    
    debates_data = [
        {
            "id": debate.id,
            "prompt": debate.prompt[:100] + "..." if len(debate.prompt) > 100 else debate.prompt,
            "created_at": debate.created_at.isoformat() if debate.created_at else None,
            "status": debate.status,
            "mode": debate.mode,
        }
        for debate in recent_debates
    ]
    
    # Feedback summary (stub for now - actual implementation would query feedback table)
    feedback_summary = {
        "total": 0,
        "helpful": 0,
        "not_helpful": 0,
    }
    
    # Patchset 57.0: Get recent debate errors from DebateError table
    from models import DebateError
    recent_errors_rows = session.exec(
        select(DebateError)
        .where(DebateError.user_id == user_id)
        .order_by(DebateError.created_at.desc())
        .limit(10)
    ).all()
    
    recent_errors = [
        {
            "debate_id": err.debate_id,
            "created_at": err.created_at.isoformat() if err.created_at else None,
            "status": err.status,
            "error_summary": err.error_summary,
        }
        for err in recent_errors_rows
    ]
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "plan": user.plan,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "is_active": user.is_active,
        },
        "quota": {
            "tokens_used_today": usage["tokens_used"],
            "daily_token_limit": limits.daily_token_limit,
            "token_usage_pct": round(usage["tokens_used"] / limits.daily_token_limit * 100, 1) if limits.daily_token_limit > 0 else 0,
            "exports_used_today": usage["exports_used"],
            "daily_export_limit": limits.daily_export_limit,
            "export_usage_pct": round(usage["exports_used"] / limits.daily_export_limit * 100, 1) if limits.daily_export_limit > 0 else 0,
        },
        "recent_debates": debates_data,
        "feedback_summary": feedback_summary,
        "recent_errors": recent_errors,
    }


@router.get("/users/{user_id}/notes")
def admin_get_user_notes(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_admin),
):
    """
    Get support notes for a user, ordered by newest first.
    """
    # Verify user exists
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    notes = session.exec(
        select(SupportNote)
        .where(SupportNote.user_id == user_id)
        .order_by(SupportNote.created_at.desc())
        .limit(limit)
    ).all()
    
    # Get author emails
    author_ids = [note.author_id for note in notes if note.author_id]
    authors = {}
    if author_ids:
        author_users = session.exec(select(User).where(User.id.in_(author_ids))).all()
        authors = {u.id: u.email for u in author_users}
    
    return {
        "notes": [
            {
                "id": note.id,
                "note": note.note,
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "author_email": authors.get(note.author_id, "Unknown") if note.author_id else "System",
            }
            for note in notes
        ]
    }


@router.post("/users/{user_id}/notes")
def admin_create_user_note(
    user_id: str,
    request: CreateNoteRequest,
    req: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Create a support note for a user.
    """
    # Verify user exists
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create note
    note = SupportNote(
        user_id=user_id,
        author_id=admin.id,
        note=request.note,
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    
    logger.info(f"Support note created by {admin.email} for user {user.email}: {note.id}")

    from audit import record_audit
    record_audit(
        "create_support_note",
        user_id=admin.id,
        target_type="user",
        target_id=user.id,
        meta={"note_id": note.id, "target_email": user.email},
        ip_address=req.client.host if req.client else None,
        session=session,
    )
    
    return {
        "id": note.id,
        "note": note.note,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "author_email": admin.email,
    }


@router.post("/users/{user_id}/status")
def admin_update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    req: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """
    Enable or disable a user account.
    Disabled users cannot create debates or use most features.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_status = user.is_active
    user.is_active = request.is_active
    session.commit()
    
    action = "enabled" if request.is_active else "disabled"
    logger.info(
        f"User account {action} by admin {admin.email}: "
        f"user={user.email} ({user.id}) old_status={old_status} new_status={request.is_active}"
    )
    
    # Create audit log
    from audit import record_audit
    record_audit(
        f"account_{action}",
        user_id=admin.id,
        target_type="user",
        target_id=user.id,
        meta={"old_status": old_status, "new_status": request.is_active, "target_email": user.email},
        ip_address=req.client.host if req.client else None,
        session=session,
    )
    
    return {
        "user_id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "message": f"Account {action} successfully",
    }
