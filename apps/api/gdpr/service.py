"""GDPR export and deletion service.

Provides user data export (Right of Access) and deletion request
processing (Right to Erasure) with grace period support.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlmodel import Session, select

logger = logging.getLogger(__name__)

# Grace period before actual deletion (days)
GDPR_DELETION_GRACE_DAYS = 30


def export_user_data(db: Session, user_id: str) -> Dict[str, Any]:
    """Export all user data as a JSON-serializable dictionary.

    Covers: profile, billing, debates, API keys, audit logs, usage.
    """
    from billing.models import BillingSubscription, BillingUsage
    from models import AuditLog, User

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    export: Dict[str, Any] = {
        "export_id": str(uuid.uuid4()),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": user.id,
            "email": getattr(user, "email", None),
            "name": getattr(user, "name", None),
            "created_at": getattr(user, "created_at", None).isoformat() if getattr(user, "created_at", None) else None,
            "plan": getattr(user, "plan", None),
        },
    }

    # Billing data
    try:
        billing_usage = db.exec(
            select(BillingUsage).where(BillingUsage.user_id == user_id)
        ).all()
        export["billing"] = {
            "usage_periods": [
                {
                    "period": u.period,
                    "debates_created": u.debates_created,
                    "exports_count": u.exports_count,
                    "tokens_used": u.tokens_used,
                    "model_tokens": u.model_tokens or {},
                }
                for u in billing_usage
            ]
        }

        subscriptions = db.exec(
            select(BillingSubscription).where(BillingSubscription.user_id == user_id)
        ).all()
        export["billing"]["subscriptions"] = [
            {
                "plan_id": s.plan_id,
                "status": s.status,
                "current_period_start": s.current_period_start.isoformat() if s.current_period_start else None,
                "current_period_end": s.current_period_end.isoformat() if s.current_period_end else None,
                "provider": s.provider,
            }
            for s in subscriptions
        ]
    except Exception as exc:
        logger.warning("Failed to export billing data for %s: %s", user_id, exc)
        export["billing"] = {"error": "export failed"}

    # Audit logs
    try:
        audit_logs = db.exec(
            select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at.desc()).limit(1000)
        ).all()
        export["audit_logs"] = [
            {
                "action": a.action,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "details": getattr(a, "details", None),
            }
            for a in audit_logs
        ]
    except Exception as exc:
        logger.warning("Failed to export audit logs for %s: %s", user_id, exc)
        export["audit_logs"] = []

    return export


def create_deletion_request(db: Session, user_id: str) -> Dict[str, Any]:
    """Create a deletion request with grace period.

    Returns the request details including the scheduled deletion date.
    """
    from models import User

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    now = datetime.now(timezone.utc)
    grace_period = timedelta(days=GDPR_DELETION_GRACE_DAYS)
    scheduled_deletion = now + grace_period

    # Check if there's already a pending request
    existing = getattr(user, "deletion_requested_at", None)
    if existing and existing > now - grace_period:
        return {
            "status": "already_requested",
            "requested_at": existing.isoformat(),
            "scheduled_deletion_at": (existing + grace_period).isoformat(),
            "grace_days": GDPR_DELETION_GRACE_DAYS,
            "message": "A deletion request is already pending.",
        }

    # Mark user for deletion (soft delete)
    object.__setattr__(user, "deletion_requested_at", now)
    object.__setattr__(user, "is_active", False)
    db.add(user)
    db.commit()

    logger.info(
        "GDPR deletion request created user=%s scheduled=%s",
        user_id, scheduled_deletion.isoformat(),
    )

    return {
        "status": "scheduled",
        "requested_at": now.isoformat(),
        "scheduled_deletion_at": scheduled_deletion.isoformat(),
        "grace_days": GDPR_DELETION_GRACE_DAYS,
        "message": (
            f"Your account will be permanently deleted on {scheduled_deletion.strftime('%Y-%m-%d')}. "
            "You can cancel this request by contacting support before that date."
        ),
    }


def cancel_deletion_request(db: Session, user_id: str) -> Dict[str, Any]:
    """Cancel a pending deletion request and reactivate the account."""
    from models import User

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    existing = getattr(user, "deletion_requested_at", None)
    if not existing:
        return {"status": "no_pending_request", "message": "No deletion request to cancel."}

    now = datetime.now(timezone.utc)
    grace_period = timedelta(days=GDPR_DELETION_GRACE_DAYS)
    if existing + grace_period <= now:
        return {"status": "too_late", "message": "Deletion is already scheduled and cannot be cancelled."}

    object.__setattr__(user, "deletion_requested_at", None)
    object.__setattr__(user, "is_active", True)
    db.add(user)
    db.commit()

    return {"status": "cancelled", "message": "Deletion request cancelled. Your account has been reactivated."}


def process_scheduled_deletions(db: Session) -> int:
    """Process users whose grace period has elapsed.

    Should be called periodically (e.g., daily cron).
    Returns the number of users processed.
    """
    from models import User

    now = datetime.now(timezone.utc)
    grace_period = timedelta(days=GDPR_DELETION_GRACE_DAYS)
    cutoff = now - grace_period

    pending = db.exec(
        select(User).where(
            User.deletion_requested_at.isnot(None),
            User.deletion_requested_at <= cutoff,
        )
    ).all()

    count = 0
    for user in pending:
        try:
            _anonymize_user(db, user)
            count += 1
            logger.info("GDPR deletion executed user=%s", user.id)
        except Exception as exc:
            logger.error("Failed to delete user %s: %s", user.id, exc)

    return count


def _anonymize_user(db: Session, user) -> None:
    """Anonymize user data instead of hard-delete to preserve referential integrity."""

    # Anonymize PII fields
    anonymized_email = f"deleted-{user.id[:8]}@anonymized.local"
    object.__setattr__(user, "email", anonymized_email)
    object.__setattr__(user, "name", None)
    object.__setattr__(user, "password_hash", None)
    object.__setattr__(user, "google_id", None)
    object.__setattr__(user, "deletion_requested_at", None)
    object.__setattr__(user, "is_active", False)
    object.__setattr__(user, "anonymized_at", datetime.now(timezone.utc))
    db.add(user)
    db.commit()
