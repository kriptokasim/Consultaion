"""
Patchset 58.0: Data Retention & Purge Jobs

Maintenance module for purging old data according to retention settings.
Intended to be called by admin endpoint or cron job.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

import sqlalchemy as sa
from models import (
    AuditLog,
    Debate,
    DebateContinuation,
    DebateError,
    DebateRound,
    DebateStageCheckpoint,
    DebateTurn,
    DivergenceReport,
    LLMUsageLog,
    Message,
    PairwiseVote,
    Score,
    SupportNote,
    UserInteraction,
    UserPrediction,
    VoteRecord,
    utcnow,
)
from sqlmodel import select

from config import settings

if TYPE_CHECKING:
    from sqlmodel import Session

logger = logging.getLogger(__name__)


def purge_old_debates(session: "Session") -> int:
    """Anonymize retained debate data older than RETAIN_DEBATES_DAYS.

    The current data model stores model output in normalized tables, not on the
    Debate row. Scrub those related rows as part of the same retention action so
    the configured retention period actually removes prompt/response content and
    direct user/team linkage while preserving aggregate, non-content analytics.
    """
    days = settings.RETAIN_DEBATES_DAYS
    if not days or days <= 0:
        logger.info("Debate retention disabled (RETAIN_DEBATES_DAYS not set)")
        return 0

    cutoff = utcnow() - timedelta(days=days)

    old_debates = session.exec(
        select(Debate)
        .where(Debate.created_at < cutoff)
        .where(Debate.prompt != "[ANONYMIZED]")
    ).all()

    if not old_debates:
        return 0

    debate_ids = [debate.id for debate in old_debates]

    for debate in old_debates:
        debate.prompt = "[ANONYMIZED]"
        debate.final_content = None
        debate.final_meta = None
        debate.config = None
        debate.panel_config = None
        debate.routing_meta = None
        debate.user_id = None
        debate.team_id = None
        session.add(debate)

    # Normalized model/user content. Keep structural rows where useful for
    # aggregate analytics, but remove free-form text and user identifiers.
    session.execute(
        sa.update(Message)
        .where(Message.debate_id.in_(debate_ids))
        .values(content="[ANONYMIZED]", persona=None, meta=None)
    )
    session.execute(
        sa.update(Score)
        .where(Score.debate_id.in_(debate_ids))
        .values(rationale="[ANONYMIZED]", meta=None)
    )
    session.execute(
        sa.update(DebateTurn)
        .where(DebateTurn.debate_id.in_(debate_ids))
        .values(claims_nodes=None, position_drift=None, moderation_steering=None)
    )
    session.execute(
        sa.update(DivergenceReport)
        .where(DivergenceReport.debate_id.in_(debate_ids))
        .values(consensus_claims=None, contested_claims=None)
    )
    session.execute(
        sa.update(DebateRound)
        .where(DebateRound.debate_id.in_(debate_ids))
        .values(note=None)
    )
    session.execute(
        sa.update(LLMUsageLog)
        .where(LLMUsageLog.debate_id.in_(debate_ids))
        .values(user_id=None, error_message=None)
    )
    session.execute(
        sa.update(PairwiseVote)
        .where(PairwiseVote.debate_id.in_(debate_ids))
        .values(user_id=None)
    )
    session.execute(
        sa.update(DebateContinuation)
        .where(DebateContinuation.debate_id.in_(debate_ids))
        .values(user_id=None, failure_detail_safe=None)
    )
    session.execute(
        sa.update(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id.in_(debate_ids))
        .values(
            execution_metadata=None,
            error_message=None,
            output_reference=None,
            owner_id=None,
        )
    )

    # User-generated interaction/vote rows add little aggregate value and retain
    # a direct user identifier, so delete them for expired debates.
    session.execute(sa.delete(UserInteraction).where(UserInteraction.debate_id.in_(debate_ids)))
    session.execute(sa.delete(UserPrediction).where(UserPrediction.debate_id.in_(debate_ids)))
    session.execute(sa.delete(VoteRecord).where(VoteRecord.debate_id.in_(debate_ids)))

    # Preserve that an audit action happened, but detach the expired decision
    # from a user and discard metadata such as IP addresses and target emails.
    session.execute(
        sa.update(AuditLog)
        .where(AuditLog.target_type == "debate")
        .where(AuditLog.target_id.in_(debate_ids))
        .values(user_id=None, meta={})
    )

    session.commit()
    logger.info("Anonymized %s debates older than %s days", len(old_debates), days)
    return len(old_debates)


def purge_old_debate_errors(session: "Session") -> int:
    """
    Delete DebateError rows older than RETAIN_DEBATE_ERRORS_DAYS.

    Returns: Number of rows deleted.
    """
    days = settings.RETAIN_DEBATE_ERRORS_DAYS
    if not days or days <= 0:
        logger.info("DebateError retention disabled")
        return 0

    cutoff = utcnow() - timedelta(days=days)

    old_errors = session.exec(
        select(DebateError)
        .where(DebateError.created_at < cutoff)
    ).all()

    count = len(old_errors)
    for error in old_errors:
        session.delete(error)

    if count > 0:
        session.commit()
        logger.info(f"Deleted {count} debate errors older than {days} days")

    return count


def purge_old_support_notes(session: "Session") -> int:
    """
    Delete SupportNotes older than RETAIN_SUPPORT_NOTES_DAYS if configured.

    Returns: Number of notes deleted (0 if retention is indefinite).
    """
    days = settings.RETAIN_SUPPORT_NOTES_DAYS
    if days is None:
        logger.info("SupportNote retention is indefinite, skipping purge")
        return 0

    if days <= 0:
        return 0

    cutoff = utcnow() - timedelta(days=days)

    old_notes = session.exec(
        select(SupportNote)
        .where(SupportNote.created_at < cutoff)
    ).all()

    count = len(old_notes)
    for note in old_notes:
        session.delete(note)

    if count > 0:
        session.commit()
        logger.info(f"Deleted {count} support notes older than {days} days")

    return count


def run_all_purges(session: "Session") -> dict:
    """
    Execute all retention purge jobs.

    Returns: Summary dict with counts per category.
    """
    logger.info("Starting data retention purge...")

    results = {
        "debates_anonymized": purge_old_debates(session),
        "debate_errors_deleted": purge_old_debate_errors(session),
        "support_notes_deleted": purge_old_support_notes(session),
    }

    logger.info(f"Retention purge complete: {results}")
    return results
