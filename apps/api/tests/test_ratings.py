import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlmodel import Session, select

from tests.utils import settings_context

sys.path.append(str(Path(__file__).resolve().parents[1]))

import config as config_module  # noqa: E402

import database  # noqa: E402
from database import init_db  # noqa: E402
from models import Debate, PairwiseVote, RatingPersona, Score  # noqa: E402
from ratings import update_ratings_for_debate, wilson_interval  # noqa: E402


@pytest.fixture(autouse=True)
def enable_ratings():
    with settings_context(DISABLE_RATINGS="0"):
        yield


@pytest.fixture
def sample_debate(db_session):
    debate = Debate(id=f"debate-{uuid.uuid4()}", prompt="Test prompt", status="completed")
    db_session.add(debate)
    db_session.commit()
    db_session.refresh(debate)
    return debate


def test_wilson_interval_behaviour():
    assert wilson_interval(10, 10)[0] > 0.5
    assert wilson_interval(0, 0) == (0.0, 0.0)
    fifty = wilson_interval(5, 10)
    assert fifty[0] < 0.5 < fifty[1]


def test_rating_update_creates_personas(db_session, sample_debate):
    persona_a = f"Alpha-{uuid.uuid4().hex}"
    persona_b = f"Beta-{uuid.uuid4().hex}"
    db_session.add(Score(debate_id=sample_debate.id, persona=persona_a, judge="Judge", score=9.0, rationale="Strong"))
    db_session.add(Score(debate_id=sample_debate.id, persona=persona_b, judge="Judge", score=6.0, rationale="Weak"))
    db_session.commit()

    update_ratings_for_debate(sample_debate.id)

    alpha = db_session.exec(select(RatingPersona).where(RatingPersona.persona == persona_a)).first()
    beta = db_session.exec(select(RatingPersona).where(RatingPersona.persona == persona_b)).first()
    assert alpha is not None and beta is not None
    assert alpha.elo > beta.elo
    assert alpha.n_matches >= 1 and beta.n_matches >= 1
    assert alpha.win_rate > beta.win_rate


def test_pairwise_votes_created(db_session, sample_debate):
    for idx, score_value in enumerate((9.0, 7.0, 5.0)):
        db_session.add(
            Score(
                debate_id=sample_debate.id,
                persona=f"Persona{idx}",
                judge="Judge",
                score=score_value,
                rationale="Rationale",
            )
        )
    db_session.commit()

    update_ratings_for_debate(sample_debate.id)

    votes = db_session.exec(select(PairwiseVote).where(PairwiseVote.debate_id == sample_debate.id)).all()
    assert len(votes) == 3


def test_category_specific_ratings(db_session, sample_debate):
    sample_debate.final_meta = {"category": "policy"}
    db_session.add(sample_debate)
    db_session.commit()

    db_session.add(Score(debate_id=sample_debate.id, persona="PolicyBot", judge="Judge", score=9.0, rationale="Great"))
    db_session.add(Score(debate_id=sample_debate.id, persona="CriticBot", judge="Judge", score=7.0, rationale="OK"))
    db_session.commit()

    update_ratings_for_debate(sample_debate.id)

    policy_row = db_session.exec(
        select(RatingPersona).where(RatingPersona.persona == "PolicyBot", RatingPersona.category == "policy")
    ).first()
    assert policy_row is not None


def test_multiple_debates_update_win_rate(db_session, sample_debate):
    other = Debate(id=f"debate-{uuid.uuid4()}", prompt="Another promt", status="completed")
    db_session.add(other)
    db_session.commit()

    db_session.add(Score(debate_id=sample_debate.id, persona="PersonaA", judge="Judge", score=9.0, rationale="Win"))
    db_session.add(Score(debate_id=sample_debate.id, persona="PersonaB", judge="Judge", score=7.0, rationale="Loss"))
    db_session.commit()
    update_ratings_for_debate(sample_debate.id)

    db_session.add(Score(debate_id=other.id, persona="PersonaA", judge="Judge", score=7.0, rationale="Loss"))
    db_session.add(Score(debate_id=other.id, persona="PersonaB", judge="Judge", score=9.0, rationale="Win"))
    db_session.commit()
    update_ratings_for_debate(other.id)

    persona_a = db_session.exec(select(RatingPersona).where(RatingPersona.persona == "PersonaA")).first()
    persona_b = db_session.exec(select(RatingPersona).where(RatingPersona.persona == "PersonaB")).first()
    assert persona_a is not None and persona_b is not None
    assert persona_a.win_rate == pytest.approx(0.5)
    assert persona_b.win_rate == pytest.approx(0.5)
