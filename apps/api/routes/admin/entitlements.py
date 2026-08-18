from __future__ import annotations

from datetime import datetime

from audit import record_audit
from auth import get_current_admin
from billing.manual_entitlements import (
    grant_manual_entitlement,
    revoke_manual_entitlements,
)
from deps import get_session
from fastapi import APIRouter, Depends, Request
from models import User
from pydantic import BaseModel, Field
from sqlmodel import Session

router = APIRouter()


class ManualEntitlementGrantRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=50)
    expires_at: datetime
    reason: str = Field(min_length=1, max_length=500)


@router.post("/users/{user_id}/entitlement")
def admin_grant_manual_entitlement(
    user_id: str,
    body: ManualEntitlementGrantRequest,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    """Grant a time-bounded non-revenue entitlement to a user.

    This is intentionally separate from Stripe-backed paid subscriptions and
    from the legacy ``User.plan`` compatibility marker. The resulting manual
    grant is a trialing entitlement with explicit source, reason, expiry and
    granting-admin metadata.
    """
    grant = grant_manual_entitlement(
        session,
        user_id=user_id,
        plan_slug=body.plan,
        granted_by_user_id=admin.id,
        reason=body.reason,
        expires_at=body.expires_at,
    )

    record_audit(
        "manual_entitlement_granted",
        user_id=admin.id,
        target_type="user",
        target_id=user_id,
        ip_address=request.client.host if request.client else None,
        meta={
            "plan": body.plan,
            "expires_at": grant.current_period_end.isoformat(),
            "source": grant.entitlement_source,
            "reason": grant.entitlement_reason,
            "subscription_id": str(grant.id),
            "revenue_entitlement": False,
        },
        session=session,
    )
    session.commit()
    session.refresh(grant)

    return {
        "user_id": user_id,
        "plan": body.plan,
        "entitlement_updated": True,
        "source": grant.entitlement_source,
        "status": grant.status,
        "expires_at": grant.current_period_end.isoformat(),
        "subscription_id": str(grant.id),
        "revenue_entitlement": False,
    }


@router.delete("/users/{user_id}/entitlement")
def admin_revoke_manual_entitlement(
    user_id: str,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    revoked = revoke_manual_entitlements(session, user_id=user_id)

    record_audit(
        "manual_entitlement_revoked",
        user_id=admin.id,
        target_type="user",
        target_id=user_id,
        ip_address=request.client.host if request.client else None,
        meta={"revoked_grants": revoked, "source": "admin_manual_grant"},
        session=session,
    )
    session.commit()

    return {
        "user_id": user_id,
        "entitlement_updated": bool(revoked),
        "revoked_grants": revoked,
    }
