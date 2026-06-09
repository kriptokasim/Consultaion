import pytest
from sqlmodel import select
from datetime import datetime, timezone

from models import Debate, User, UserPrediction, Score, UserInteraction
from worker.voting_tasks import _execute_vote_reasons_extraction


def test_cast_prediction_success(authenticated_client, db_session, monkeypatch):
    """Test creating, updating, and locking a prediction successfully."""
    monkeypatch.setattr("routes.voting.require_llm_action_allowed", lambda **kwargs: None)
    debate_id = "test-voting-debate-1"
    
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=debate_id,
        user_id=user.id,
        prompt="Who is better?",
        status="running",
        mode="voting",
        config={}
    )
    db_session.add(debate)
    db_session.commit()

    # Cast initial prediction
    payload = {
        "predicted_winner": "ModelA",
        "confidence_score": 0.6,
        "is_locked": False
    }
    resp = authenticated_client.post(f"/api/v1/voting/{debate_id}/predict", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["prediction"]["predicted_winner"] == "ModelA"
    assert data["prediction"]["is_locked"] is False

    # Update prediction (still unlocked)
    payload_update = {
        "predicted_winner": "ModelB",
        "confidence_score": 0.8,
        "is_locked": True
    }
    resp_update = authenticated_client.post(f"/api/v1/voting/{debate_id}/predict", json=payload_update)
    assert resp_update.status_code == 200
    data_update = resp_update.json()
    assert data_update["prediction"]["predicted_winner"] == "ModelB"
    assert data_update["prediction"]["is_locked"] is True

    # Try updating again now that it is locked
    resp_fail = authenticated_client.post(f"/api/v1/voting/{debate_id}/predict", json={
        "predicted_winner": "ModelA",
        "confidence_score": 0.9,
        "is_locked": False
    })
    assert resp_fail.status_code == 400
    assert "locked" in resp_fail.json()["error"]["message"]

    # Verify UserInteraction logs
    db_session.expire_all()
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    interaction = db_session.exec(
        select(UserInteraction).where(
            UserInteraction.debate_id == debate_id,
            UserInteraction.interaction_type == "voting_prediction"
        )
    ).all()
    assert len(interaction) >= 2
    assert interaction[-1].user_id == user.id
    assert interaction[-1].details["predicted_winner"] == "ModelB"


def test_cast_prediction_completed_debate(authenticated_client, db_session, monkeypatch):
    """Test that predictions are disabled once a debate is completed."""
    monkeypatch.setattr("routes.voting.require_llm_action_allowed", lambda **kwargs: None)
    debate_id = "test-voting-debate-completed"
    
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=debate_id,
        user_id=user.id,
        prompt="Who won?",
        status="completed",
        mode="voting",
        config={}
    )
    db_session.add(debate)
    db_session.commit()

    resp = authenticated_client.post(f"/api/v1/voting/{debate_id}/predict", json={
        "predicted_winner": "ModelA",
        "confidence_score": 0.5
    })
    assert resp.status_code == 400
    assert "completed" in resp.json()["error"]["message"]


@pytest.mark.anyio
async def test_reveal_prediction_and_reasons(authenticated_client, db_session, monkeypatch):
    """Test prediction resolution and LLM reason extraction during reveal."""
    monkeypatch.setattr("routes.voting.require_llm_action_allowed", lambda **kwargs: None)
    debate_id = "test-voting-debate-reveal"
    
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=debate_id,
        user_id=user.id,
        prompt="Speed of Light?",
        status="completed",
        mode="voting",
        config={}
    )
    db_session.add(debate)

    # User prediction
    prediction = UserPrediction(
        debate_id=debate_id,
        user_id=user.id,
        predicted_winner="EinsteinModel",
        confidence_score=0.9,
        is_locked=True
    )
    db_session.add(prediction)

    # Pre-seed other predictions for Wilson aggregates
    pred2 = UserPrediction(
        debate_id=debate_id,
        user_id="another-user-1",
        predicted_winner="EinsteinModel",
        confidence_score=0.8,
        is_locked=True
    )
    pred3 = UserPrediction(
        debate_id=debate_id,
        user_id="another-user-2",
        predicted_winner="NewtonModel",
        confidence_score=0.4,
        is_locked=True
    )
    db_session.add(pred2)
    db_session.add(pred3)

    # Scores / Rationales
    score1 = Score(
        debate_id=debate_id,
        persona="EinsteinModel",
        judge="JudgeAlpha",
        score=9.5,
        rationale="Very accurate and elegant reasoning about relativity."
    )
    score2 = Score(
        debate_id=debate_id,
        persona="NewtonModel",
        judge="JudgeAlpha",
        score=8.0,
        rationale="Classic mechanics are good but relativistic limit missed."
    )
    db_session.add(score1)
    db_session.add(score2)
    db_session.commit()

    # Mock LLM vote reasons task
    async def mock_extract(prompt, content, model_name, deb_id):
        # We don't need a real LLM call here, just let worker task save dummy data
        pass

    # Mock call_llm_for_role to return specific highlights
    async def mock_call_llm(messages, role, temperature, max_tokens, debate_id):
        return '{"winner_highlights": ["Elegance", "Accuracy"], "dissenter_highlights": ["Lacks relativity"]}', None

    monkeypatch.setattr("worker.voting_tasks.call_llm_for_role", mock_call_llm)

    # Call reveal route
    resp = authenticated_client.get(f"/api/v1/voting/{debate_id}/reveal")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["prediction"]["is_correct"] is True
    assert data["prediction"]["resolved_at"] is not None
    
    # Check Wilson score bounds and percentage aggregates
    aggregates = data["aggregates"]
    assert len(aggregates) == 2
    einstein_agg = next(a for a in aggregates if a["candidate"] == "EinsteinModel")
    assert einstein_agg["percentage"] == 66.7
    assert einstein_agg["wilson_lower"] > 0.0
    assert einstein_agg["wilson_upper"] < 1.0

    # Check vote reasons extracted
    reasons = data["vote_reasons"]
    assert reasons is not None
    assert "Elegance" in reasons["winner_highlights"]
    assert "Lacks relativity" in reasons["dissenter_highlights"]
