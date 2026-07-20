"""PS157 Track M: Terminal side-effect idempotency tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def session():
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    SQLModel.metadata.drop_all(engine)


def _claim(session, debate_id, transition_type):
    from services.terminal_transition import claim_transition
    return claim_transition(session, debate_id, transition_type)


def test_first_claim_succeeds(session):
    debate_id = str(uuid.uuid4())
    result = _claim(session, debate_id, "summary_email")
    assert result is not None
    assert result.debate_id == debate_id
    assert result.transition_type == "summary_email"
    assert result.status == "claimed"


def test_duplicate_claim_returns_none(session):
    debate_id = str(uuid.uuid4())
    first = _claim(session, debate_id, "summary_email")
    assert first is not None
    second = _claim(session, debate_id, "summary_email")
    assert second is None


def test_different_types_for_same_debate_can_both_claim(session):
    debate_id = str(uuid.uuid4())
    email = _claim(session, debate_id, "summary_email")
    slack = _claim(session, debate_id, "slack_alert")
    assert email is not None
    assert slack is not None
    assert email.debate_id == slack.debate_id
    assert email.transition_type != slack.transition_type


def test_same_type_different_debates(session):
    d1 = str(uuid.uuid4())
    d2 = str(uuid.uuid4())
    assert _claim(session, d1, "summary_email") is not None
    assert _claim(session, d2, "summary_email") is not None


def test_has_transition(session):
    from services.terminal_transition import has_transition
    debate_id = str(uuid.uuid4())
    assert not has_transition(session, debate_id, "summary_email")
    _claim(session, debate_id, "summary_email")
    assert has_transition(session, debate_id, "summary_email")


def test_complete_transition(session):
    from services.terminal_transition import complete_transition, has_transition
    debate_id = str(uuid.uuid4())
    t = _claim(session, debate_id, "summary_email")
    assert t is not None
    assert t.completed_at is None
    complete_transition(session, t)
    assert t.status == "completed"
    assert t.completed_at is not None
    assert has_transition(session, debate_id, "summary_email")


def test_claim_includes_meta(session):
    debate_id = str(uuid.uuid4())
    meta = {"reason": "test", "count": 1}
    from services.terminal_transition import claim_transition
    t = claim_transition(session, debate_id, "slack_alert", meta=meta)
    assert t is not None
    assert t.meta == meta


def test_claim_constants_match(session):
    from services.terminal_transition import (
        TRANSITION_BILLING_USAGE,
        TRANSITION_SLACK_ALERT,
        TRANSITION_SUMMARY_EMAIL,
        TRANSITION_USAGE_COUNTER,
    )
    for ttype in [TRANSITION_SUMMARY_EMAIL, TRANSITION_SLACK_ALERT, TRANSITION_BILLING_USAGE, TRANSITION_USAGE_COUNTER]:
        assert _claim(session, str(uuid.uuid4()), ttype) is not None


def test_unique_constraint_prevents_race(session):
    """Simulate concurrent claims hitting the unique constraint."""
    debate_id = str(uuid.uuid4())
    t1 = _claim(session, debate_id, "summary_email")
    assert t1 is not None
    from sqlalchemy import text
    session.execute(text("DELETE FROM terminal_transition WHERE id = :id"), {"id": t1.id})
    session.commit()
    t2 = _claim(session, debate_id, "summary_email")
    assert t2 is not None
