from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from billing.models import ReferralAttribution
from models import User, utcnow
from sqlmodel import Session, select

REFERRAL_TTL_DAYS = 30
_MAX_TOKEN_LENGTH = 256


def _token_hash(token: str) -> str | None:
    value = (token or "").strip()
    if not value or len(value) > _MAX_TOKEN_LENGTH:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def issue_referral_token(
    session: Session,
    *,
    debate_id: str,
    created_by_user_id: str,
) -> tuple[str, ReferralAttribution]:
    """Create a one-way-hashed referral token for a public decision artifact."""
    now = utcnow()
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
    """Atomically record a public-share visit without visitor identity or IP."""
    digest = _token_hash(token)
    if digest is None:
        return False

    now = utcnow()
    stmt = (
        sa.update(ReferralAttribution)
        .where(ReferralAttribution.token_hash == digest)
        .where(ReferralAttribution.expires_at > now)
        .values(
            view_count=ReferralAttribution.view_count + 1,
            visited_at=sa.case(
                (ReferralAttribution.visited_at.is_(None), now),
                else_=ReferralAttribution.visited_at,
            ),
            last_visited_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    session.flush()
    return bool(result.rowcount)


def claim_referral(
    session: Session,
    *,
    token: str,
    user_id: str,
) -> bool:
    """Atomically attribute a referral to the first *newly-created* account.

    Existing users opening a public link must never inflate investor acquisition
    metrics. A claim is therefore eligible only when the account was created on
    or after the referral token was issued. The conditional UPDATE remains the
    concurrency authority for two newly-created users racing to claim one token.
    """
    digest = _token_hash(token)
    if digest is None:
        return False

    now = utcnow()
    referral = session.exec(
        select(ReferralAttribution).where(ReferralAttribution.token_hash == digest)
    ).first()
    if referral is None or _as_utc(referral.expires_at) <= _as_utc(now):
        return False

    if referral.claimed_by_user_id:
        return referral.claimed_by_user_id == user_id

    user = session.get(User, user_id)
    if user is None:
        return False
    if _as_utc(user.created_at) < _as_utc(referral.created_at):
        # This account predates the share link: engagement, not acquisition.
        return False

    stmt = (
        sa.update(ReferralAttribution)
        .where(ReferralAttribution.token_hash == digest)
        .where(ReferralAttribution.expires_at > now)
        .where(ReferralAttribution.claimed_by_user_id.is_(None))
        .values(
            claimed_by_user_id=user_id,
            claimed_at=now,
            visited_at=sa.case(
                (ReferralAttribution.visited_at.is_(None), now),
                else_=ReferralAttribution.visited_at,
            ),
            last_visited_at=sa.case(
                (ReferralAttribution.last_visited_at.is_(None), now),
                else_=ReferralAttribution.last_visited_at,
            ),
            view_count=sa.case(
                (ReferralAttribution.view_count < 1, 1),
                else_=ReferralAttribution.view_count,
            ),
        )
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    session.flush()
    if result.rowcount:
        return True

    existing = session.exec(
        select(ReferralAttribution.claimed_by_user_id)
        .where(ReferralAttribution.token_hash == digest)
        .where(ReferralAttribution.expires_at > now)
    ).first()
    if isinstance(existing, tuple):
        existing = existing[0]
    return existing == user_id
