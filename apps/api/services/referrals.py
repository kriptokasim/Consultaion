from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from billing.models import ReferralAttribution
from models import utcnow
from sqlmodel import Session, select

REFERRAL_TTL_DAYS = 30
_MAX_TOKEN_LENGTH = 256


def _token_hash(token: str) -> str | None:
    value = (token or "").strip()
    if not value or len(value) > _MAX_TOKEN_LENGTH:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_referral_token(
    session: Session,
    *,
    debate_id: str,
    created_by_user_id: str,
) -> tuple[str, ReferralAttribution]:
    """Create a one-way-hashed referral token for a public decision artifact."""
    now = utcnow()
    # 192 bits of entropy before URL-safe base64 expansion.
    raw_token = secrets.token_urlsafe(24)
    digest = _token_hash(raw_token)
    assert digest is not None

    row = ReferralAttribution(
        token_hash=digest,
        debate_id=debate_id,
        created_by_user_id=created_by_user_id,
        expires_at=now + timedelta(days=REFERRAL_TTL_DAYS),
        created_at=now,
    )
    session.add(row)
    session.flush()
    return raw_token, row


def record_referral_visit(session: Session, *, token: str) -> bool:
    """Record a public-share visit without storing visitor identity or IP."""
    digest = _token_hash(token)
    if digest is None:
        return False

    now = utcnow()
    row = session.exec(
        select(ReferralAttribution).where(ReferralAttribution.token_hash == digest)
    ).first()
    if row is None or row.expires_at <= now:
        return False

    row.view_count = int(row.view_count or 0) + 1
    if row.visited_at is None:
        row.visited_at = now
    row.last_visited_at = now
    session.add(row)
    session.flush()
    return True


def claim_referral(
    session: Session,
    *,
    token: str,
    user_id: str,
) -> bool:
    """Claim a referral token for the first authenticated user, idempotently."""
    digest = _token_hash(token)
    if digest is None:
        return False

    now = utcnow()
    row = session.exec(
        select(ReferralAttribution).where(ReferralAttribution.token_hash == digest)
    ).first()
    if row is None or row.expires_at <= now:
        return False

    if row.claimed_by_user_id:
        return row.claimed_by_user_id == user_id

    # A direct CTA click can reach signup before the best-effort visit beacon
    # finishes. Treat claim as an implicit unique visit in that race rather than
    # losing attribution.
    if row.visited_at is None:
        row.visited_at = now
        row.last_visited_at = now
        row.view_count = max(1, int(row.view_count or 0))

    row.claimed_by_user_id = user_id
    row.claimed_at = now
    session.add(row)
    session.flush()
    return True
