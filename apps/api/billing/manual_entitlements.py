from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from exceptions import NotFoundError, ValidationError
from models import User, utcnow
from sqlmodel import Session, select

from billing.models import BillingPlan, BillingSubscription

MANUAL_PROVIDER = "manual"
MANUAL_STATUS = "trialing"
MANUAL_SOURCE = "admin_manual_grant"
MAX_MANUAL_GRANT_DAYS = 30


def _normalize_expiry(expires_at: datetime) -> datetime:
    if expires_at.tzinfo is None:
        raise ValidationError(
            message="expires_at must include an explicit timezone",
            code="billing.manual_expiry_timezone_required",
        )
    return expires_at.astimezone(timezone.utc)


def grant_manual_entitlement(
    session: Session,
    *,
    user_id: str,
    plan_slug: str,
    granted_by_user_id: str,
    reason: str,
    expires_at: datetime,
) -> BillingSubscription:
    """Stage a time-bounded non-revenue entitlement grant.

    Manual grants are represented as ``provider='manual'`` and
    ``status='trialing'`` BillingSubscription rows. ``get_active_plan`` already
    treats trialing as entitled, while investor MRR counts only ``active`` rows,
    so a support/comp grant cannot be mistaken for paid revenue.

    To keep precedence deterministic with the current single paid tier, grants
    are allowed only when no effective non-manual subscription exists and are
    capped at 30 days. A later paid monthly/annual subscription naturally has a
    later period end and therefore becomes the selected entitlement.
    """
    now = utcnow()
    expiry = _normalize_expiry(expires_at)
    reason_value = reason.strip()

    if not reason_value:
        raise ValidationError(
            message="A reason is required for manual entitlement grants",
            code="billing.manual_reason_required",
        )
    if len(reason_value) > 500:
        raise ValidationError(
            message="Manual entitlement reason is too long",
            code="billing.manual_reason_too_long",
        )
    if expiry <= now:
        raise ValidationError(
            message="Manual entitlement expiry must be in the future",
            code="billing.manual_expiry_invalid",
        )
    if expiry > now + timedelta(days=MAX_MANUAL_GRANT_DAYS):
        raise ValidationError(
            message=f"Manual entitlement grants may not exceed {MAX_MANUAL_GRANT_DAYS} days",
            code="billing.manual_expiry_too_far",
        )

    user = session.get(User, user_id)
    if not user:
        raise NotFoundError(message="User not found", code="billing.user_not_found")

    plan = session.exec(select(BillingPlan).where(BillingPlan.slug == plan_slug)).first()
    if not plan:
        raise ValidationError(
            message=f"Unknown billing plan '{plan_slug}'",
            code="billing.plan_not_found",
        )
    if plan.is_default_free:
        raise ValidationError(
            message="Use manual-entitlement revoke to return a user to the default free plan",
            code="billing.manual_free_not_allowed",
        )

    active_provider_subscription = session.exec(
        select(BillingSubscription)
        .where(BillingSubscription.user_id == user_id)
        .where(BillingSubscription.provider != MANUAL_PROVIDER)
        .where(BillingSubscription.status.in_(["active", "trialing"]))
        .where(BillingSubscription.current_period_start <= now)
        .where(BillingSubscription.current_period_end > now)
    ).first()
    if active_provider_subscription:
        raise ValidationError(
            message="User already has an active provider-backed entitlement",
            code="billing.manual_conflicts_with_provider_subscription",
            status_code=409,
        )

    # Replace any previous manual grant rather than stacking multiple trial rows.
    existing_manual = session.exec(
        select(BillingSubscription)
        .where(BillingSubscription.user_id == user_id)
        .where(BillingSubscription.provider == MANUAL_PROVIDER)
        .where(BillingSubscription.status.in_(["active", "trialing"]))
    ).all()
    for existing in existing_manual:
        existing.status = "canceled"
        existing.updated_at = now
        session.add(existing)

    grant = BillingSubscription(
        user_id=user_id,
        plan_id=plan.id,
        status=MANUAL_STATUS,
        current_period_start=now,
        current_period_end=expiry,
        cancel_at_period_end=False,
        provider=MANUAL_PROVIDER,
        provider_subscription_id=f"manual:{uuid.uuid4()}",
        entitlement_source=MANUAL_SOURCE,
        entitlement_reason=reason_value,
        granted_by_user_id=granted_by_user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(grant)

    # Compatibility marker only. Authorization still resolves BillingSubscription.
    user.plan = plan.slug
    session.add(user)
    session.flush()
    return grant


def revoke_manual_entitlements(session: Session, *, user_id: str) -> int:
    """Stage revocation of all currently entitled manual grants for a user."""
    user = session.get(User, user_id)
    if not user:
        raise NotFoundError(message="User not found", code="billing.user_not_found")

    now = utcnow()
    grants = session.exec(
        select(BillingSubscription)
        .where(BillingSubscription.user_id == user_id)
        .where(BillingSubscription.provider == MANUAL_PROVIDER)
        .where(BillingSubscription.status.in_(["active", "trialing"]))
    ).all()

    for grant in grants:
        grant.status = "canceled"
        grant.updated_at = now
        session.add(grant)

    session.flush()

    # With manual grants removed, recompute the compatibility marker from the
    # same canonical resolver used by authorization and quota enforcement.
    from billing.service import get_active_plan

    user.plan = get_active_plan(session, user_id).slug
    session.add(user)
    return len(grants)


def cleanup_expired_manual_entitlements(
    session: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Cancel expired manual grants and resync affected compatibility markers.

    Entitlement authorization already ignores out-of-period rows. This cleanup
    keeps admin/user-facing legacy ``User.plan`` state from remaining stale after
    a time-bounded grant expires. The function stages changes and leaves commit
    ownership to the maintenance caller.
    """
    cutoff = (now or utcnow()).astimezone(timezone.utc)
    expired = session.exec(
        select(BillingSubscription)
        .where(BillingSubscription.provider == MANUAL_PROVIDER)
        .where(BillingSubscription.status.in_(["active", "trialing"]))
        .where(BillingSubscription.current_period_end <= cutoff)
    ).all()

    if not expired:
        return 0

    affected_user_ids = {grant.user_id for grant in expired}
    for grant in expired:
        grant.status = "canceled"
        grant.updated_at = cutoff
        session.add(grant)

    # Flush cancellation first so canonical resolution cannot select the expired
    # manual row while compatibility markers are being recomputed.
    session.flush()

    from billing.service import get_active_plan

    for user_id in affected_user_ids:
        user = session.get(User, user_id)
        if not user:
            continue
        user.plan = get_active_plan(session, user_id).slug
        session.add(user)

    session.flush()
    return len(expired)
