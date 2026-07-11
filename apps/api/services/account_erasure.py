"""Canonical account erasure service.

Single implementation used by both immediate deletion (/auth/me)
and scheduled GDPR deletion. Ensures consistent behavior and
prevents drift between the two paths.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import sqlalchemy as sa
from auth import hash_password
from models import (
    APIKey,
    AuditLog,
    ChallengeRound,
    ChallengeSession,
    ConversationVote,
    Debate,
    DebateAttempt,
    DebateRound,
    DebateStageCheckpoint,
    DebateTurn,
    LLMUsageLog,
    Message,
    OracleBranch,
    OracleSession,
    PairwiseVote,
    RedTeamSession,
    Score,
    SupportNote,
    TeamMember,
    User,
    UserInteraction,
    UserPrediction,
    UserProviderKey,
    UsageCounter,
    UsageLedgerEntry,
    UsageQuota,
    Vote,
    VoteRecord,
    utcnow,
)
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

# Valid anonymized email domain — non-routable
_ANONYMIZED_DOMAIN = "invalid.local"


@dataclass
class AccountErasureResult:
    user_id: str
    debates_anonymized: int
    api_keys_deleted: bool
    provider_keys_deleted: bool
    completed_at: datetime


def erase_user_account(
    session: Session,
    user: User,
    *,
    reason: str = "user_request",
) -> AccountErasureResult:
    """Erase all user-owned data and anonymize the user record.

    Caller controls commit/rollback. This function stages all changes
    on the session but does NOT commit.

    Args:
        session: Active SQLModel session.
        user: The User ORM instance to erase.
        reason: Audit label (e.g. "user_request", "gdpr_scheduled").

    Returns:
        AccountErasureResult with counts for audit logging.
    """
    user_id = user.id
    deleted_email = f"deleted+{secrets.token_hex(8)}@{_ANONYMIZED_DOMAIN}"

    # ── C1: User anonymization ──────────────────────────────────────
    user.email = deleted_email
    user.display_name = None
    user.avatar_url = None
    user.bio = None
    user.timezone = None
    user.email_summaries_enabled = False
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.deletion_requested_at = None
    user.deleted_at = utcnow()
    user.is_active = False
    # Reset lockout metadata
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_failed_login_at = None
    session.add(user)

    # ── C2: Delete direct user-owned records ────────────────────────
    session.execute(sa.delete(APIKey).where(APIKey.user_id == user_id))
    session.execute(sa.delete(UserProviderKey).where(UserProviderKey.user_id == user_id))
    session.execute(sa.delete(SupportNote).where(SupportNote.author_id == user_id))
    # Anonymize support notes ABOUT the user (retained for support history)
    session.execute(
        sa.update(SupportNote)
        .where(SupportNote.user_id == user_id)
        .values(user_id=None, note="[User deleted]")
    )
    session.execute(sa.delete(UserInteraction).where(UserInteraction.user_id == user_id))
    session.execute(sa.delete(UserPrediction).where(UserPrediction.user_id == user_id))
    session.execute(sa.delete(TeamMember).where(TeamMember.user_id == user_id))
    session.execute(sa.delete(UsageCounter).where(UsageCounter.user_id == user_id))
    session.execute(sa.delete(UsageQuota).where(UsageQuota.user_id == user_id))
    session.execute(sa.delete(LLMUsageLog).where(LLMUsageLog.user_id == user_id))
    session.execute(sa.delete(UsageLedgerEntry).where(UsageLedgerEntry.user_id == user_id))
    session.execute(sa.delete(ConversationVote).where(ConversationVote.user_id == user_id))

    # Challenge/oracle/red-team sessions
    session.execute(sa.delete(ChallengeRound).where(
        ChallengeRound.session_id.in_(
            sa.select(ChallengeSession.id).where(ChallengeSession.user_id == user_id)
        )
    ))
    session.execute(sa.delete(ChallengeSession).where(ChallengeSession.user_id == user_id))
    session.execute(sa.delete(OracleBranch).where(
        OracleBranch.session_id.in_(
            sa.select(OracleSession.id).where(OracleSession.user_id == user_id)
        )
    ))
    session.execute(sa.delete(OracleSession).where(OracleSession.user_id == user_id))
    session.execute(sa.delete(RedTeamSession).where(RedTeamSession.user_id == user_id))

    # Debate attempts via subquery
    session.execute(sa.delete(DebateAttempt).where(DebateAttempt.debate_id.in_(
        sa.select(Debate.id).where(Debate.user_id == user_id)
    )))
    # Debate stage checkpoints
    session.execute(sa.delete(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id.in_(
        sa.select(Debate.id).where(Debate.user_id == user_id)
    )))

    # ── Anonymize retained Debate data ──────────────────────────────
    user_debates = session.exec(
        select(Debate).where(Debate.user_id == user_id)
    ).all()
    debate_ids = [d.id for d in user_debates]
    anonymized_count = 0
    for debate in user_debates:
        if debate.prompt != "[DELETED]":
            debate.prompt = "[DELETED]"
            debate.final_content = None
            debate.final_meta = None
            debate.config = None
            debate.panel_config = None
            debate.user_id = None
            anonymized_count += 1
    session.add_all(user_debates)

    # ── Anonymize/delete related debate data ────────────────────────
    if debate_ids:
        session.execute(
            sa.update(Message)
            .where(Message.debate_id.in_(debate_ids))
            .values(content="[DELETED]", persona=None, meta=None)
        )
        session.execute(sa.delete(Score).where(Score.debate_id.in_(debate_ids)))
        session.execute(sa.delete(Vote).where(Vote.debate_id.in_(debate_ids)))
        session.execute(sa.delete(PairwiseVote).where(PairwiseVote.debate_id.in_(debate_ids)))
        session.execute(sa.delete(VoteRecord).where(VoteRecord.debate_id.in_(debate_ids)))
        session.execute(sa.delete(DebateRound).where(DebateRound.debate_id.in_(debate_ids)))
        session.execute(sa.delete(DebateTurn).where(DebateTurn.debate_id.in_(debate_ids)))

    # ── Scrub PII from retained AuditLog metadata ──────────────────
    PII_KEYS = {"email", "ip_address", "ip", "remote_addr", "email_address"}
    audit_logs = session.exec(
        select(AuditLog).where(AuditLog.user_id == user_id)
    ).all()
    for log in audit_logs:
        if log.meta:
            scrubbed = {}
            for k, v in log.meta.items():
                if k.lower() in PII_KEYS:
                    scrubbed[k] = "[REDACTED]"
                elif isinstance(v, dict):
                    # Recursively scrub nested PII
                    scrubbed[k] = {
                        nk: "[REDACTED]" if nk.lower() in PII_KEYS else nv
                        for nk, nv in v.items()
                    }
                else:
                    scrubbed[k] = v
            log.meta = scrubbed
            session.add(log)

    return AccountErasureResult(
        user_id=user_id,
        debates_anonymized=anonymized_count,
        api_keys_deleted=True,
        provider_keys_deleted=True,
        completed_at=utcnow(),
    )
