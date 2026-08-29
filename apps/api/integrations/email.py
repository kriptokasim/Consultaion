import httpx
from loguru import logger
from schemas import DebateSummary

from config import settings

RESEND_API_BASE = "https://api.resend.com"


def is_email_summaries_enabled() -> bool:
    return settings.ENABLE_EMAIL_SUMMARIES and bool(settings.RESEND_API_KEY)


def _complete_summary_transition(debate_id: str) -> None:
    """Persist provider acknowledgement for crash-reclaimable email delivery."""
    try:
        from database import session_scope
        from services.terminal_transition import (
            TRANSITION_SUMMARY_EMAIL,
            complete_transition_by_key,
        )

        with session_scope() as session:
            complete_transition_by_key(
                session,
                debate_id,
                TRANSITION_SUMMARY_EMAIL,
            )
    except Exception:
        logger.warning(
            "Failed to complete summary-email transition for debate %s",
            debate_id,
            exc_info=True,
        )


async def send_debate_summary_email(
    user_email: str,
    summary: DebateSummary,
) -> bool:
    """Send one summary email and return whether delivery was acknowledged.

    Disabled delivery is treated as a successful no-op. Provider/transport
    failures return False so maintenance reconciliation can retry a stale claim.
    """
    if not is_email_summaries_enabled():
        logger.debug("Email summaries disabled; skipping send.")
        _complete_summary_transition(summary.debate_id)
        return True

    api_key = settings.RESEND_API_KEY
    if not api_key:
        logger.warning("Email summaries enabled but RESEND_API_KEY missing; skipping send.")
        return False

    subject = f"[Consultaion] Debate summary – {summary.title}"
    html = f"""
    <h1>Debate summary</h1>
    <p><strong>Title:</strong> {summary.title}</p>
    <p><strong>Models used:</strong> {", ".join(summary.models_used)}</p>
    {"<p><strong>Winner:</strong> " + summary.winner + "</p>" if summary.winner else ""}
    <p>{summary.summary_text}</p>
    {f'<p><a href="{summary.url}">View in Consultaion</a></p>' if summary.url else ""}
    """

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{RESEND_API_BASE}/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": __import__("os").environ.get("EMAIL_FROM", "noreply@consultaion.com"),
                    "to": [user_email],
                    "subject": subject,
                    "html": html,
                },
            )
        resp.raise_for_status()
        _complete_summary_transition(summary.debate_id)
        logger.info("Sent debate summary email to %s for debate %s", user_email, summary.debate_id)
        return True
    except Exception as exc:  # best-effort for caller; reconciler handles retry
        logger.warning("Failed to send debate summary email: %r", exc)
        return False
