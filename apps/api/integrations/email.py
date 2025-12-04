from typing import Optional
import httpx
from loguru import logger

from core.settings import settings
from schemas import DebateSummary

RESEND_API_BASE = "https://api.resend.com"

def is_email_summaries_enabled() -> bool:
    cfg = settings.notifications
    return cfg.enable_email_summaries and bool(cfg.resend_api_key)

async def send_debate_summary_email(
    user_email: str,
    summary: DebateSummary,
) -> None:
    if not is_email_summaries_enabled():
        logger.debug("Email summaries disabled; skipping send.")
        return

    api_key = settings.notifications.resend_api_key
    if not api_key:
        logger.warning("Email summaries enabled but RESEND_API_KEY missing; skipping send.")
        return

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
                    "from": "noreply@consultaion.local",  # TODO: configure
                    "to": [user_email],
                    "subject": subject,
                    "html": html,
                },
            )
        resp.raise_for_status()
        logger.info("Sent debate summary email to %s for debate %s", user_email, summary.debate_id)
    except Exception as exc:  # best-effort only
        logger.warning("Failed to send debate summary email: %r", exc)
