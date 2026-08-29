"""Prevent prior-attempt terminal output from leaking into an active full retry."""

from __future__ import annotations

import logging
from copy import deepcopy

from models import Debate, DebateAttempt
from sqlmodel import select

logger = logging.getLogger(__name__)

_installed = False
_original_dispatch = None


def _clear_stale_terminal_payload_for_new_attempt(debate_id: str):
    """Clear prior final output only when a newer queued logical attempt exists."""
    from database import session_scope

    with session_scope() as session:
        debate = session.exec(
            select(Debate).where(Debate.id == debate_id).with_for_update()
        ).first()
        if debate is None:
            return None
        current_attempt = max(int(debate.run_attempt or 0), 1)
        queued = session.exec(
            select(DebateAttempt)
            .where(
                DebateAttempt.debate_id == debate_id,
                DebateAttempt.attempt_number > current_attempt,
                DebateAttempt.status == "queued",
            )
            .order_by(DebateAttempt.attempt_number.asc())
            .limit(1)
        ).first()
        if queued is None:
            return None

        previous = (debate.final_content, deepcopy(debate.final_meta))
        debate.final_content = None
        debate.final_meta = None
        session.add(debate)
        session.commit()
        logger.info(
            "retry.presentation_payload_cleared debate_id=%s source_attempt=%s target_attempt=%s",
            debate_id,
            current_attempt,
            queued.attempt_number,
        )
        return previous


def _restore_terminal_payload(debate_id: str, previous) -> None:
    if previous is None:
        return
    from database import session_scope

    with session_scope() as session:
        debate = session.exec(
            select(Debate).where(Debate.id == debate_id).with_for_update()
        ).first()
        if debate is None:
            return
        debate.final_content, debate.final_meta = previous
        session.add(debate)
        session.commit()


async def _guarded_dispatch_debate_run(*args, **kwargs):
    debate_id = str(args[0] if args else kwargs.get("debate_id") or "")
    resume = bool(kwargs.get("resume", False))
    continuation_id = kwargs.get("continuation_id")

    previous = None
    # Full retries create a newer queued DebateAttempt. Staged continuation and
    # crash takeover reuse the current attempt and must retain current output.
    if debate_id and resume and not continuation_id:
        previous = _clear_stale_terminal_payload_for_new_attempt(debate_id)

    try:
        return await _original_dispatch(*args, **kwargs)
    except Exception:
        if previous is not None:
            try:
                _restore_terminal_payload(debate_id, previous)
            except Exception:
                logger.exception(
                    "retry.presentation_payload_restore_failed debate_id=%s",
                    debate_id,
                )
        raise


def install_retry_presentation_guard() -> None:
    global _installed, _original_dispatch
    if _installed:
        return

    import debate_dispatch

    _original_dispatch = debate_dispatch.dispatch_debate_run
    debate_dispatch.dispatch_debate_run = _guarded_dispatch_debate_run
    _installed = True
