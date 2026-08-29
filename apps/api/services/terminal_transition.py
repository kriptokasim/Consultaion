"""Durable idempotency claims for debate terminal side effects.

A claim is not the same thing as a completed external side effect. Workers may
crash after claiming but before an email/webhook provider acknowledges the
request, so claims are renewable after a bounded stale window and are marked
``completed`` only by the side-effect integration after provider success.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from models import TerminalTransition
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

TRANSITION_SUMMARY_EMAIL = "summary_email"
TRANSITION_SLACK_ALERT = "slack_alert"
TRANSITION_BILLING_USAGE = "billing_usage"
TRANSITION_USAGE_COUNTER = "usage_counter"

# Long enough that a normal provider request finishes before another worker may
# retry, but bounded so a crash between claim and provider acknowledgement does
# not suppress the side effect forever.
TERMINAL_TRANSITION_CLAIM_TTL_SECONDS = 300


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def claim_transition(
    session: Session,
    debate_id: str,
    transition_type: str,
    meta: Optional[dict[str, Any]] = None,
) -> TerminalTransition | None:
    """Atomically claim or reclaim one terminal side effect.

    Fresh claims are protected by the unique ``(debate_id, transition_type)``
    identity. A completed row is final. A still-fresh claimed row belongs to a
    live/possibly-live worker and is not stolen. A stale claimed row is locked
    and renewed so crash recovery can retry the external side effect.
    """
    now = datetime.now(timezone.utc)
    transition = TerminalTransition(
        id=str(uuid.uuid4()),
        debate_id=debate_id,
        transition_type=transition_type,
        status="claimed",
        created_at=now,
        meta=meta,
    )
    session.add(transition)
    try:
        session.flush()
        return transition
    except IntegrityError:
        session.rollback()

    existing = session.exec(
        select(TerminalTransition)
        .where(
            TerminalTransition.debate_id == debate_id,
            TerminalTransition.transition_type == transition_type,
        )
        .with_for_update()
    ).first()
    if existing is None:
        # The conflicting row disappeared between rollback and re-read. Let the
        # caller retry rather than inventing an unfenced side effect.
        return None
    if existing.status == "completed":
        return None

    stale_before = now - timedelta(seconds=TERMINAL_TRANSITION_CLAIM_TTL_SECONDS)
    if existing.status == "claimed" and _as_utc(existing.created_at) > stale_before:
        return None

    existing.status = "claimed"
    existing.created_at = now
    existing.completed_at = None
    if meta is not None:
        existing.meta = meta
    session.add(existing)
    session.flush()
    logger.warning(
        "terminal_transition.reclaimed debate_id=%s transition_type=%s",
        debate_id,
        transition_type,
    )
    return existing


async def claim_transition_async(
    debate_id: str,
    transition_type: str,
    meta: Optional[dict[str, Any]] = None,
    session_factory=None,
) -> bool:
    """Async wrapper returning whether this worker owns the side-effect claim."""
    from database import session_scope as sync_session_scope

    loop = asyncio.get_running_loop()

    def _do_claim() -> bool:
        with sync_session_scope() as session:
            return claim_transition(session, debate_id, transition_type, meta) is not None

    return await loop.run_in_executor(None, _do_claim)


def complete_transition(session: Session, transition: TerminalTransition) -> None:
    """Mark an owned claim completed after the external side effect succeeds."""
    transition.status = "completed"
    transition.completed_at = datetime.now(timezone.utc)
    session.add(transition)
    session.flush()


def complete_transition_by_key(
    session: Session,
    debate_id: str,
    transition_type: str,
) -> bool:
    """Complete the durable identity used by integrations after provider ack."""
    transition = session.exec(
        select(TerminalTransition)
        .where(
            TerminalTransition.debate_id == debate_id,
            TerminalTransition.transition_type == transition_type,
        )
        .with_for_update()
    ).first()
    if transition is None:
        return False
    if transition.status == "completed":
        return False
    complete_transition(session, transition)
    return True


def has_transition(
    session: Session,
    debate_id: str,
    transition_type: str,
) -> bool:
    """Return whether a terminal-transition identity exists."""
    result = session.exec(
        select(TerminalTransition).where(
            TerminalTransition.debate_id == debate_id,
            TerminalTransition.transition_type == transition_type,
        )
    ).first()
    return result is not None
