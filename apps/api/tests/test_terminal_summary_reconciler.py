from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.anyio
async def test_stale_summary_claim_is_completed_when_delivery_is_disabled(db_session, monkeypatch):
    from config import settings
    from models import Debate, TerminalTransition, User
    from services.terminal_transition import (
        TERMINAL_TRANSITION_CLAIM_TTL_SECONDS,
        TRANSITION_SUMMARY_EMAIL,
    )
    from worker.terminal_tasks import _reconcile_stale_summary_email_claims

    user = User(
        id="terminal-summary-user",
        email="summary@example.com",
        password_hash="test",
        email_summaries_enabled=True,
    )
    debate = Debate(
        id="terminal-summary-debate",
        prompt="terminal summary reconcile",
        status="completed",
        user_id=user.id,
        final_content="final answer",
        final_meta={"ranking": ["A"]},
    )
    transition = TerminalTransition(
        debate_id=debate.id,
        transition_type=TRANSITION_SUMMARY_EMAIL,
        status="claimed",
        created_at=datetime.now(timezone.utc)
        - timedelta(seconds=TERMINAL_TRANSITION_CLAIM_TTL_SECONDS + 1),
    )
    db_session.add_all([user, debate, transition])
    db_session.commit()

    monkeypatch.setattr(settings, "ENABLE_EMAIL_SUMMARIES", False)

    reconciled = await _reconcile_stale_summary_email_claims()

    db_session.expire_all()
    stored = db_session.get(TerminalTransition, transition.id)
    assert reconciled == 1
    assert stored.status == "completed"
    assert stored.completed_at is not None
