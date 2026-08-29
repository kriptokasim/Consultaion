from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from schemas import DebateSummary
from sqlmodel import select

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _reconcile_stale_summary_email_claims(limit: int = 50) -> int:
    """Retry stale summary-email claims left behind by crashed workers."""
    from database import session_scope
    from integrations.email import send_debate_summary_email
    from models import Debate, TerminalTransition, User
    from services.terminal_transition import (
        TERMINAL_TRANSITION_CLAIM_TTL_SECONDS,
        TRANSITION_SUMMARY_EMAIL,
        claim_transition,
        complete_transition_by_key,
    )

    stale_before = datetime.now(timezone.utc) - timedelta(
        seconds=TERMINAL_TRANSITION_CLAIM_TTL_SECONDS
    )

    with session_scope() as session:
        stale_rows = list(
            session.exec(
                select(TerminalTransition)
                .where(
                    TerminalTransition.transition_type == TRANSITION_SUMMARY_EMAIL,
                    TerminalTransition.status == "claimed",
                    TerminalTransition.created_at <= stale_before,
                )
                .order_by(TerminalTransition.created_at.asc())
                .limit(max(int(limit), 1))
            ).all()
        )
        identities = [(row.debate_id, row.transition_type) for row in stale_rows]

    reconciled = 0
    for debate_id, transition_type in identities:
        with session_scope() as session:
            owned = claim_transition(session, debate_id, transition_type)
            if owned is None:
                continue

            debate = session.get(Debate, debate_id)
            if debate is None or not debate.user_id:
                complete_transition_by_key(session, debate_id, transition_type)
                continue
            user = session.get(User, debate.user_id)
            if user is None or not user.email or not user.email_summaries_enabled:
                complete_transition_by_key(session, debate_id, transition_type)
                continue

            models = set()
            if debate.model_id:
                models.add(debate.model_id)
            if debate.routed_model:
                models.add(debate.routed_model)
            winner = None
            if isinstance(debate.final_meta, dict):
                ranking = debate.final_meta.get("ranking")
                if isinstance(ranking, list) and ranking:
                    winner = str(ranking[0])

            summary = DebateSummary(
                debate_id=str(debate.id),
                title=debate.prompt[:100] if debate.prompt else "Unnamed Debate",
                models_used=sorted(models),
                winner=winner,
                summary_text=(debate.final_content or "No summary available.")[:2000],
                url=None,
            )
            email = user.email

        delivered = await send_debate_summary_email(email, summary)
        if delivered:
            reconciled += 1
        else:
            logger.warning(
                "terminal.summary_email_reconcile_failed debate_id=%s",
                debate_id,
            )

    return reconciled


@celery_app.task(name="maintenance.reconcile_terminal_summary_emails", bind=True, max_retries=3)
def reconcile_terminal_summary_emails(self) -> int:
    try:
        return asyncio.run(_reconcile_stale_summary_email_claims())
    except Exception as exc:
        logger.exception("Failed to reconcile stale summary-email claims")
        raise self.retry(exc=exc, countdown=60) from exc
