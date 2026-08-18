"""Canonical account erasure service.

Single implementation used by both immediate deletion (/auth/me)
and scheduled GDPR deletion. Ensures consistent behavior and
prevents drift between the two paths.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Session, select

from auth import hash_password
from models import (
    APIKey,
    AdminEvent,
    AuditLog,
    ChallengeRound,
    ChallengeSession,
    CodingLaneResult,
    CodingPatchArtifact,
    CodingRun,
    CodingTurn,
    ConversationVote,
    Debate,
    DebateAttempt,
    DebateContinuation,
    DebateError,
    DebateRound,
    DebateStageCheckpoint,
    DebateTurn,
    DivergenceReport,
    LLMUsageLog,
    Message,
    OracleBranch,
    OracleSession,
    PairwiseVote,
    RedTeamSession,
    Score,
    SupportNote,
    TeamMember,
    TerminalTransition,
    UsageCounter,
    UsageLedgerEntry,
    UsageQuota,
    User,
    UserInteraction,
    UserPrediction,
    UserProviderKey,
    Vote,
    VoteRecord,
    utcnow,
)

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


PII_KEYS = {"email", "ip_address", "ip", "remote_addr", "email_address"}


def _scrub_pii(value):
    """Recursively redact PII-bearing keys in JSON-compatible metadata."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).lower() in PII_KEYS else _scrub_pii(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_pii(item) for item in value]
    return value


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
    session.execute(sa.delete(DebateError).where(DebateError.user_id == user_id))

    # Coding-agent artifacts can contain user prompts, source diffs, and model output.
    coding_run_ids = sa.select(CodingRun.id).where(CodingRun.user_id == user_id)
    session.execute(
        sa.delete(CodingPatchArtifact).where(CodingPatchArtifact.coding_run_id.in_(coding_run_ids))
    )
    session.execute(
        sa.delete(CodingLaneResult).where(CodingLaneResult.coding_run_id.in_(coding_run_ids))
    )
    session.execute(sa.delete(CodingTurn).where(CodingTurn.coding_run_id.in_(coding_run_ids)))
    session.execute(sa.delete(CodingRun).where(CodingRun.user_id == user_id))

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

    # Debate attempts and stage checkpoints via subquery
    owned_debate_ids = sa.select(Debate.id).where(Debate.user_id == user_id)
    session.execute(sa.delete(DebateAttempt).where(DebateAttempt.debate_id.in_(owned_debate_ids)))
    session.execute(
        sa.delete(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id.in_(owned_debate_ids))
    )

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
            debate.routing_meta = None
            debate.team_id = None
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
        session.execute(sa.delete(DivergenceReport).where(DivergenceReport.debate_id.in_(debate_ids)))
        session.execute(
            sa.update(DebateContinuation)
            .where(DebateContinuation.debate_id.in_(debate_ids))
            .values(user_id=None, failure_detail_safe=None)
        )
        session.execute(
            sa.update(TerminalTransition)
            .where(TerminalTransition.debate_id.in_(debate_ids))
            .values(meta=None)
        )
        session.execute(
            sa.update(AdminEvent)
            .where(AdminEvent.debate_id.in_(debate_ids))
            .values(message="[User deleted]", meta=None)
        )

    # ── Scrub PII from retained AuditLog metadata ──────────────────
    audit_logs = session.exec(
        select(AuditLog).where(AuditLog.user_id == user_id)
    ).all()
    for log in audit_logs:
        if log.meta:
            log.meta = _scrub_pii(log.meta)
            session.add(log)

    return AccountErasureResult(
        user_id=user_id,
        debates_anonymized=anonymized_count,
        api_keys_deleted=True,
        provider_keys_deleted=True,
        completed_at=utcnow(),
    )
