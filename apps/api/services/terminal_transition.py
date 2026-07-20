"""PS157 Track M: Idempotent claim service for debate terminal side effects.

Ensures that each terminal side effect (summary email, Slack alert,
billing increment) is applied at most once per debate, even across
worker crash-recovery cycles.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from models import TerminalTransition
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

TRANSITION_SUMMARY_EMAIL = "summary_email"
TRANSITION_SLACK_ALERT = "slack_alert"
TRANSITION_BILLING_USAGE = "billing_usage"
TRANSITION_USAGE_COUNTER = "usage_counter"


def claim_transition(
    session: Session,
    debate_id: str,
    transition_type: str,
    meta: Optional[dict[str, Any]] = None,
) -> TerminalTransition | None:
    """Atomically claim a terminal transition for this debate.

    Returns the TerminalTransition row if the claim was acquired (first caller),
    or None if another worker already claimed it.
    """
    transition = TerminalTransition(
        id=str(uuid.uuid4()),
        debate_id=debate_id,
        transition_type=transition_type,
        status="claimed",
        created_at=datetime.now(timezone.utc),
        meta=meta,
    )
    session.add(transition)
    try:
        session.flush()
        return transition
    except IntegrityError:
        session.rollback()
        return None


async def claim_transition_async(
    debate_id: str,
    transition_type: str,
    meta: Optional[dict[str, Any]] = None,
    session_factory=None,
) -> bool:
    """Async wrapper for claim_transition using a sync session scope.

    Returns True if this worker acquired the claim, False if already claimed.
    """
    from database import session_scope as sync_session_scope

    loop = asyncio.get_running_loop()

    def _do_claim() -> bool:
        with sync_session_scope() as session:
            return claim_transition(session, debate_id, transition_type, meta) is not None

    return await loop.run_in_executor(None, _do_claim)


def complete_transition(session: Session, transition: TerminalTransition) -> None:
    """Mark a claimed transition as completed.

    Best-effort — the unique constraint on (debate_id, transition_type)
    prevents duplicates regardless of this update.
    """
    transition.status = "completed"
    transition.completed_at = datetime.now(timezone.utc)
    session.add(transition)
    session.flush()


def has_transition(
    session: Session,
    debate_id: str,
    transition_type: str,
) -> bool:
    """Check if a transition has already been claimed."""
    result = session.exec(
        select(TerminalTransition).where(
            TerminalTransition.debate_id == debate_id,
            TerminalTransition.transition_type == transition_type,
        )
    ).first()
    return result is not None
