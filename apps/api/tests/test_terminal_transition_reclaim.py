from datetime import datetime, timedelta, timezone


def test_fresh_terminal_claim_is_not_stolen(db_session):
    from services.terminal_transition import (
        TRANSITION_SUMMARY_EMAIL,
        claim_transition,
    )

    first = claim_transition(
        db_session,
        "debate-terminal-fresh",
        TRANSITION_SUMMARY_EMAIL,
    )
    db_session.commit()
    assert first is not None

    second = claim_transition(
        db_session,
        "debate-terminal-fresh",
        TRANSITION_SUMMARY_EMAIL,
    )
    assert second is None


def test_stale_terminal_claim_is_reclaimable(db_session):
    from services.terminal_transition import (
        TERMINAL_TRANSITION_CLAIM_TTL_SECONDS,
        TRANSITION_SUMMARY_EMAIL,
        claim_transition,
    )

    first = claim_transition(
        db_session,
        "debate-terminal-stale",
        TRANSITION_SUMMARY_EMAIL,
    )
    db_session.commit()
    assert first is not None

    first.created_at = datetime.now(timezone.utc) - timedelta(
        seconds=TERMINAL_TRANSITION_CLAIM_TTL_SECONDS + 1
    )
    db_session.add(first)
    db_session.commit()

    reclaimed = claim_transition(
        db_session,
        "debate-terminal-stale",
        TRANSITION_SUMMARY_EMAIL,
    )
    assert reclaimed is not None
    assert reclaimed.id == first.id
    assert reclaimed.status == "claimed"


def test_completed_terminal_claim_is_never_reclaimed(db_session):
    from services.terminal_transition import (
        TRANSITION_SUMMARY_EMAIL,
        claim_transition,
        complete_transition,
    )

    first = claim_transition(
        db_session,
        "debate-terminal-completed",
        TRANSITION_SUMMARY_EMAIL,
    )
    assert first is not None
    complete_transition(db_session, first)
    db_session.commit()

    duplicate = claim_transition(
        db_session,
        "debate-terminal-completed",
        TRANSITION_SUMMARY_EMAIL,
    )
    assert duplicate is None
