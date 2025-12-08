"""
Patchset 58.0: Data Retention & Purge Jobs

Maintenance module for purging old data according to retention settings.
Intended to be called by admin endpoint or cron job.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from config import settings
from models import Debate, DebateError, SupportNote, utcnow
from sqlmodel import select

if TYPE_CHECKING:
    from sqlmodel import Session

logger = logging.getLogger(__name__)


def purge_old_debates(session: "Session") -> int:
    """
    Anonymize debates older than RETAIN_DEBATES_DAYS.
    
    Strategy: Clear prompt/messages content but keep metadata for analytics.
    This preserves aggregate stats while removing PII.
    
    Returns: Number of debates anonymized.
    """
    days = settings.RETAIN_DEBATES_DAYS
    if not days or days <= 0:
        logger.info("Debate retention disabled (RETAIN_DEBATES_DAYS not set)")
        return 0
    
    cutoff = utcnow() - timedelta(days=days)
    
    # Find old debates that haven't been anonymized yet
    old_debates = session.exec(
        select(Debate)
        .where(Debate.created_at < cutoff)
        .where(Debate.prompt != "[ANONYMIZED]")  # Skip already processed
    ).all()
    
    count = 0
    for debate in old_debates:
        # Anonymize content, keep metadata
        debate.prompt = "[ANONYMIZED]"
        # Note: messages is JSON, clear if it exists
        if hasattr(debate, "messages") and debate.messages:
            debate.messages = None
        count += 1
    
    if count > 0:
        session.commit()
        logger.info(f"Anonymized {count} debates older than {days} days")
    
    return count


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
