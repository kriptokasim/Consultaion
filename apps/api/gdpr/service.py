"""GDPR export and deletion service.

Provides user data export (Right of Access) and deletion request
processing (Right to Erasure) with grace period support.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlmodel import Session, col, select

logger = logging.getLogger(__name__)

# Grace period before actual deletion (days)
GDPR_DELETION_GRACE_DAYS = 30


def export_user_data(db: Session, user_id: str) -> Dict[str, Any]:
    """Export all user data as a JSON-serializable dictionary.

    Covers: profile, billing, debates, API keys, audit logs, usage.
    Excludes: password hashes, provider-key ciphertext, raw API secrets.
    """
    from billing.models import BillingSubscription, BillingUsage
    from models import (
        APIKey,
        AuditLog,
        Debate,
        LLMUsageLog,
        UsageCounter,
        User,
        UserProviderKey,
    )

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    export: Dict[str, Any] = {
        "export_id": str(uuid.uuid4()),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "bio": user.bio,
            "timezone": user.timezone,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "plan": user.plan,
            "analytics_opt_out": user.analytics_opt_out,
            "email_summaries_enabled": user.email_summaries_enabled,
            "deletion_requested_at": user.deletion_requested_at.isoformat() if user.deletion_requested_at else None,
            "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        },
    }

    # Debates (anonymized content not included — only structural metadata)
    try:
        debates = db.exec(
            select(Debate).where(Debate.user_id == user_id).order_by(Debate.created_at.desc()).limit(500)
        ).all()
        export["debates"] = [
            {
                "id": d.id,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "mode": d.mode,
            }
            for d in debates
        ]
    except Exception as exc:
        logger.warning("Failed to export debates for %s: %s", user_id, exc)
        export["debates"] = []

    # API keys (metadata only, no secrets)
    try:
        api_keys = db.exec(
            select(APIKey).where(APIKey.user_id == user_id)
        ).all()
        export["api_keys"] = [
            {
                "id": k.id,
                "name": k.name,
                "prefix": k.prefix,
                "created_at": k.created_at.isoformat() if k.created_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            }
            for k in api_keys
        ]
    except Exception as exc:
        logger.warning("Failed to export API keys for %s: %s", user_id, exc)
        export["api_keys"] = []

    # Provider keys (metadata only, no encrypted material)
    try:
        provider_keys = db.exec(
            select(UserProviderKey).where(UserProviderKey.user_id == user_id)
        ).all()
        export["provider_keys"] = [
            {
                "id": k.id,
                "provider": k.provider,
                "masked_key": k.masked_key,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
            for k in provider_keys
        ]
    except Exception as exc:
        logger.warning("Failed to export provider keys for %s: %s", user_id, exc)
        export["provider_keys"] = []

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

    # Usage counters
    try:
        usage_counters = db.exec(
            select(UsageCounter).where(UsageCounter.user_id == user_id)
        ).all()
        export["usage"] = [
            {
                "period": u.period,
                "runs_used": u.runs_used,
                "tokens_used": u.tokens_used,
                "exports_used": u.exports_used,
            }
            for u in usage_counters
        ]
    except Exception as exc:
        logger.warning("Failed to export usage for %s: %s", user_id, exc)
        export["usage"] = []

    # LLM usage logs (metadata only)
    try:
        llm_logs = db.exec(
            select(LLMUsageLog).where(LLMUsageLog.user_id == user_id).order_by(LLMUsageLog.created_at.desc()).limit(200)
        ).all()
        export["llm_usage"] = [
            {
                "provider": l.provider,
                "model": l.model,
                "total_tokens": l.total_tokens,
                "cost_usd": l.cost_usd,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in llm_logs
        ]
    except Exception as exc:
        logger.warning("Failed to export LLM usage for %s: %s", user_id, exc)
        export["llm_usage"] = []

    # Audit logs (PII already scrubbed at write time in erasure, but export raw for user)
    try:
        audit_logs = db.exec(
            select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at.desc()).limit(1000)
        ).all()
        export["audit_logs"] = [
            {
                "action": a.action,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "meta": a.meta,
            }
            for a in audit_logs
        ]
    except Exception as exc:
        logger.warning("Failed to export audit logs for %s: %s", user_id, exc)
        export["audit_logs"] = []

    return export


def create_deletion_request(db: Session, user_id: str) -> Dict[str, Any]:
    """Create a deletion request with grace period.

    Sets deletion_requested_at but keeps the user active so they can
    cancel during the grace period.
    """
    from models import User

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    now = datetime.now(timezone.utc)
    grace_period = timedelta(days=GDPR_DELETION_GRACE_DAYS)
    scheduled_deletion = now + grace_period

    # Check if there's already a pending request
    existing = user.deletion_requested_at
    if existing and existing > now - grace_period:
        return {
            "status": "already_requested",
            "requested_at": existing.isoformat(),
            "scheduled_deletion_at": (existing + grace_period).isoformat(),
            "grace_days": GDPR_DELETION_GRACE_DAYS,
            "message": "A deletion request is already pending.",
        }

    # B2: Set deletion_requested_at but keep is_active = True
    user.deletion_requested_at = now
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
    """Cancel a pending deletion request and keep the account active."""
    from models import User

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    existing = user.deletion_requested_at
    if not existing:
        return {"status": "no_pending_request", "message": "No deletion request to cancel."}

    now = datetime.now(timezone.utc)
    grace_period = timedelta(days=GDPR_DELETION_GRACE_DAYS)
    if existing + grace_period <= now:
        return {"status": "too_late", "message": "Deletion is already scheduled and cannot be cancelled."}

    # B3: Clear timestamp and ensure active
    user.deletion_requested_at = None
    user.is_active = True
    db.add(user)
    db.commit()

    return {"status": "cancelled", "message": "Deletion request cancelled. Your account has been reactivated."}


def process_scheduled_deletions(db: Session) -> Dict[str, int]:
    """Process users whose grace period has elapsed.

    Each user is processed in an isolated savepoint so one failure
    does not block others. Returns processed and failed counts.
    """
    from models import User
    from services.account_erasure import erase_user_account

    now = datetime.now(timezone.utc)
    grace_period = timedelta(days=GDPR_DELETION_GRACE_DAYS)
    cutoff = now - grace_period

    # B4: Query against the persisted column, exclude already-deleted users
    # B5: Use FOR UPDATE SKIP LOCKED to prevent concurrent processing
    pending = db.exec(
        select(User).where(
            User.deletion_requested_at.isnot(None),
            User.deletion_requested_at <= cutoff,
            User.deleted_at.is_(None),
        ).with_for_update(skip_locked=True)
    ).all()

    processed_count = 0
    failed_count = 0

    for user in pending:
        # B5: Isolated transaction per user via savepoint
        savepoint = None
        try:
            savepoint = db.begin_nested()
            erase_user_account(db, user, reason="gdpr_scheduled")
            savepoint.commit()
            processed_count += 1
            logger.info("GDPR scheduled deletion executed user=%s", user.id)
        except Exception as exc:
            if savepoint is not None:
                try:
                    savepoint.rollback()
                except Exception:
                    pass
            failed_count += 1
            logger.error("Failed to delete user %s: %s", user.id, exc)

    # Persist the outer transaction. Releasing nested savepoints alone does not
    # survive Session.close(), because get_session() does not auto-commit.
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"processed_count": processed_count, "failed_count": failed_count}
