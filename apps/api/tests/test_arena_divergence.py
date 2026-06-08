import asyncio
import pytest
from sqlmodel import select

from models import Debate, Message, DivergenceReport, VoteRecord, UserInteraction, User
from worker.arena_tasks import _execute_divergence_computation, compute_string_similarity


def test_similarity_algorithm():
    """Verify compute_string_similarity returns high score for similar claims and low for distinct ones."""
    claim1 = "The model uses sequence matching to detect agreement."
    claim2 = "A sequence matching model detects consensus between texts."
    claim3 = "Python is a dynamic programming language."
    
    assert compute_string_similarity(claim1, claim2) >= 0.5
    assert compute_string_similarity(claim1, claim3) < 0.4


@pytest.mark.anyio
async def test_compute_divergence_success(db_session, monkeypatch):
    """Test background task computing divergence from candidate responses."""
    debate_id = "test-divergence-debate-1"
    
    debate = Debate(
        id=debate_id,
        user_id="user-123",
        prompt="Should we deploy on Fridays?",
        status="completed",
        mode="arena",
        config={}
    )
    db_session.add(debate)
    
    # Add candidate model responses
    msg1 = Message(
        debate_id=debate_id,
        round_index=1,
        role="arena_response",
        persona="GPT-4o",
        content="Deploying on Fridays is high risk. It leads to weekend support incidents. Keep deploys to Monday-Thursday."
    )
    msg2 = Message(
        debate_id=debate_id,
        round_index=1,
        role="arena_response",
        persona="Claude-3.5",
        content="Friday deployments present elevated operational risks. We should restrict deployments to Mon-Thu to prevent weekend incidents."
    )
    msg3 = Message(
        debate_id=debate_id,
        round_index=1,
        role="arena_response",
        persona="Gemini Pro",
        content="Deploying on Friday is perfectly fine if you have automated testing, canary rollouts, and a robust CI/CD pipeline."
    )
    
    db_session.add(msg1)
    db_session.add(msg2)
    db_session.add(msg3)
    db_session.commit()
    
    # Mock LLM claim extraction for testing
    async def mock_extract(prompt, content, model_name, deb_id):
        if "GPT-4o" in model_name or "Claude" in model_name:
            return ["Deploying on Fridays is high risk", "Restricting deploys to Mon-Thu prevents weekend incidents"]
        if "Gemini" in model_name:
            return ["Deploying on Fridays is fine with robust automation", "Automation and canary releases mitigate deploy risk"]
        return ["Unknown claim"]

    monkeypatch.setattr("worker.arena_tasks._extract_claims_from_response", mock_extract)
    
    # Execute divergence task
    await _execute_divergence_computation(debate_id)
    
    db_session.expire_all()
    report = db_session.exec(select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)).first()
    
    assert report is not None
    assert report.divergence_score > 0.0
    assert len(report.consensus_claims.get("claims", [])) >= 1
    assert len(report.contested_claims.get("claims", [])) >= 1


def test_get_divergence_report_endpoint(authenticated_client, db_session):
    """Test getting divergence report successfully and fallback on-the-fly calculation."""
    debate_id = "test-divergence-debate-2"
    
    debate = Debate(
        id=debate_id,
        user_id="user-123",
        prompt="Another question?",
        status="completed",
        mode="arena",
        config={}
    )
    db_session.add(debate)
    db_session.commit()
    
    # Pre-seed DivergenceReport
    report = DivergenceReport(
        debate_id=debate_id,
        divergence_score=0.4,
        consensus_claims={"claims": [{"claim": "Consensus point A", "models": ["GPT-4o", "Claude"]}]},
        contested_claims={"claims": [{"claim": "Unique point B", "model": "Gemini"}]}
    )
    db_session.add(report)
    db_session.commit()
    
    # Call GET route
    resp = authenticated_client.get(f"/api/v1/arena/{debate_id}/divergence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["divergence_score"] == 0.4
    assert data["ready"] is True
    assert len(data["consensus_claims"]["claims"]) == 1


def test_get_divergence_report_on_the_fly(authenticated_client, db_session, monkeypatch):
    """Test GET route triggers on-the-fly calculation if completed but report is missing."""
    debate_id = "test-divergence-debate-3"
    
    debate = Debate(
        id=debate_id,
        user_id="user-123",
        prompt="Is Rust faster than Python?",
        status="completed",
        mode="arena",
        config={}
    )
    db_session.add(debate)
    
    # Add messages so it has data to compute
    msg = Message(
        debate_id=debate_id,
        round_index=1,
        role="arena_response",
        persona="ModelX",
        content="Rust is faster due to native compilation and no garbage collection."
    )
    db_session.add(msg)
    db_session.commit()
    
    # Mock task computation to execute synchronously
    async def mock_compute(deb_id):
        # Insert report into db
        rep = DivergenceReport(
            debate_id=deb_id,
            divergence_score=0.0,
            consensus_claims={"claims": [{"claim": "Rust is fast", "models": ["ModelX"]}]},
            contested_claims={"claims": []}
        )
        db_session.add(rep)
        db_session.commit()
            
    monkeypatch.setattr("routes.arena._execute_divergence_computation", mock_compute)
    
    # Request GET report
    resp = authenticated_client.get(f"/api/v1/arena/{debate_id}/divergence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["divergence_score"] == 0.0
    assert data["ready"] is True
    assert len(data["consensus_claims"]["claims"]) == 1


def test_cast_arena_vote_success(authenticated_client, db_session):
    """Test casting user vote on a claim."""
    debate_id = "test-divergence-debate-4"
    
    debate = Debate(
        id=debate_id,
        user_id="user-123",
        prompt="Yes or No?",
        status="completed",
        mode="arena",
        config={}
    )
    db_session.add(debate)
    db_session.commit()
    
    payload = {
        "claim_text": "We should use Postgres.",
        "model_name": "PostgresModel",
        "is_consensus": False
    }
    
    resp = authenticated_client.post(f"/api/v1/arena/{debate_id}/user-vote", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    
    # Verify DB records
    db_session.expire_all()
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    vote = db_session.exec(select(VoteRecord).where(VoteRecord.debate_id == debate_id)).first()
    assert vote is not None
    assert vote.user_id == user.id
    assert vote.vote_json["claim_text"] == "We should use Postgres."
    
    interaction = db_session.exec(
        select(UserInteraction).where(
            UserInteraction.debate_id == debate_id,
            UserInteraction.interaction_type == "arena_vote"
        )
    ).first()
    assert interaction is not None
    assert interaction.user_id == user.id
    assert interaction.details["model_name"] == "PostgresModel"
    
    # Duplicate vote must fail
    dup_resp = authenticated_client.post(f"/api/v1/arena/{debate_id}/user-vote", json=payload)
    assert dup_resp.status_code == 400
