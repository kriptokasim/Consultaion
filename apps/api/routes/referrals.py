from __future__ import annotations

from auth import get_current_user
from deps import get_session
from exceptions import RateLimitError
from fastapi import APIRouter, Depends, Request
from models import User
from pydantic import BaseModel, Field
from ratelimit import increment_ip_bucket
from services.referrals import claim_referral, record_referral_visit
from sqlmodel import Session

from config import settings

router = APIRouter(tags=["referrals"])


def csrf_exempt(func):
    """Mark an unauthenticated attribution beacon as CSRF-exempt."""
    func.csrf_exempt = True
    return func


class ReferralTokenRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


@csrf_exempt
@router.post("/referrals/visit")
async def referral_visit(
    body: ReferralTokenRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    """Record a public-share visit without persisting visitor identity or IP."""
    ip = request.client.host if request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(
        ip,
        settings.RL_WINDOW,
        settings.RL_MAX_CALLS,
    )
    if not allowed:
        raise RateLimitError(
            message="Rate limit exceeded",
            code="rate_limit.exceeded",
            retry_after_seconds=retry_after,
        )

    # Deliberately return the same shape for valid, invalid and expired tokens;
    # the endpoint must not become a token-validity oracle.
    record_referral_visit(session, token=body.token)
    session.commit()
    return {"accepted": True}


@router.post("/referrals/claim")
async def referral_claim(
    body: ReferralTokenRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Idempotently bind a referral to the first authenticated user."""
    claimed = claim_referral(session, token=body.token, user_id=current_user.id)
    session.commit()
    return {"claimed": claimed}
