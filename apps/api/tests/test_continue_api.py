import pytest
from unittest.mock import patch, MagicMock, ANY
from models import Debate, User, DebateContinuation, LLMUsageLog
from sqlmodel import select
from datetime import datetime, timezone


def test_continue_conditional_transition(authenticated_client, db_session):
    # Get user
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # 1. Test invalid source status: "queued"
    debate_queued = Debate(
        id="test-continue-queued",
        user_id=user.id,
        prompt="Test prompt",
        status="queued",
    )
    db_session.add(debate_queued)
    db_session.commit()

    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate_queued.id}/continue")
        assert response.status_code == 400
        mock_dispatch.assert_not_called()

    # 2. Test valid source status: "perspectives_ready"
    debate_paused = Debate(
        id="test-continue-paused",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate_paused)
    db_session.commit()

    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate_paused.id}/continue")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"
        mock_dispatch.assert_called_once_with(
            "test-continue-paused",
            "Test prompt",
            "debate:test-continue-paused",
            {},
            None,
            trace_id=None,
            resume=True,
            continuation_id=ANY,
        )

        # Check DB status is updated to scheduled
        db_session.refresh(debate_paused)
        assert debate_paused.status == "scheduled"

    # 3. Test sending again (now that it is "scheduled") -> should conflict
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate_paused.id}/continue")
        assert response.status_code == 400
        mock_dispatch.assert_not_called()


def test_continue_idempotency_key(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id="test-continue-idem",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    headers = {"X-Idempotency-Key": "test-idem-key-123"}

    # First call - should succeed and dispatch
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers
        )
        assert response.status_code == 200
        mock_dispatch.assert_called_once()

        # Verify continuation record
        continuation = db_session.exec(
            select(DebateContinuation).where(
                DebateContinuation.debate_id == debate.id,
                DebateContinuation.idempotency_key == "test-idem-key-123"
            )
        ).first()
        assert continuation is not None
        assert continuation.status == "dispatched"

    # Second call (with same key) - should act as no-op and NOT dispatch again
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers
        )
        assert response.status_code == 200
        # Debate status is currently scheduled, but continuation status is dispatched
        assert response.json()["status"] == "dispatched"
        mock_dispatch.assert_not_called()

    # If it is marked as failed, retry should reset the same record to requested
    old_cont_id = continuation.id
    continuation.status = "failed"
    db_session.add(continuation)
    db_session.commit()

    # Move debate back to failed so it's a valid source state
    debate.status = "failed"
    db_session.add(debate)
    db_session.commit()

    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/continue",
            headers=headers
        )
        print("Idempotency retry response:", response.json())
        assert response.status_code == 200
        mock_dispatch.assert_called_once()

        # Verify the SAME continuation record was reset and dispatched
        db_session.refresh(continuation)
        assert continuation.id == old_cont_id
        assert continuation.status == "dispatched"


def test_continue_preflight_budget(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # Create a debate with strict budget limit (cost = 1.0)
    debate = Debate(
        id="test-continue-budget",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
        config={"budget": {"max_cost_usd": 1.0, "max_tokens": 1000}}
    )
    db_session.add(debate)
    db_session.commit()

    # Case 1: Within budget -> should pass
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate.id}/continue")
        assert response.status_code == 200
        mock_dispatch.assert_called_once()

    # Move debate back to perspectives_ready for Case 2
    db_session.refresh(debate)
    debate.status = "perspectives_ready"
    db_session.add(debate)
    db_session.commit()

    # Add usage log that exceeds budget (e.g., cost_usd = 1.5)
    usage = LLMUsageLog(
        debate_id=debate.id,
        user_id=user.id,
        provider="openai",
        model="gpt-4o",
        prompt_tokens=500,
        completion_tokens=500,
        total_tokens=1000,
        cost_usd=1.5
    )
    db_session.add(usage)
    db_session.commit()

    # Case 2: Exceeded budget -> should fail with ValidationError
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate.id}/continue")
        assert response.status_code == 400
        assert "cost limit exceeded" in response.json()["error"]["message"]
        mock_dispatch.assert_not_called()


def test_continue_preflight_circuit_breaker(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id="test-continue-circuit",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    # Mock health state to indicate circuit breaker is open (unhealthy)
    with patch("parliament.provider_health.get_health_state") as mock_get_health, \
         patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        
        mock_health = MagicMock()
        mock_health.is_open.return_value = True
        mock_get_health.return_value = mock_health

        response = authenticated_client.post(f"/api/v1/debates/{debate.id}/continue")
        assert response.status_code == 400
        assert "Circuit breaker open" in response.json()["error"]["message"]
        mock_dispatch.assert_not_called()


def test_retry_debate_run(authenticated_client, db_session):
    from models import DebateStageCheckpoint, Score, Vote, Message
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # Create failed debate
    debate = Debate(
        id="test-retry-debate",
        user_id=user.id,
        prompt="Test prompt",
        status="failed",
    )
    db_session.add(debate)
    db_session.commit()

    # Add checkpoints
    cp_draft = DebateStageCheckpoint(debate_id=debate.id, stage_key="draft", status="completed", input_hash="h1")
    cp_critique = DebateStageCheckpoint(debate_id=debate.id, stage_key="critique", status="completed", input_hash="h2")
    cp_judge = DebateStageCheckpoint(debate_id=debate.id, stage_key="judge", status="failed", input_hash="h3")
    
    db_session.add(cp_draft)
    db_session.add(cp_critique)
    db_session.add(cp_judge)
    
    # Add dummy scores/votes
    score = Score(debate_id=debate.id, persona="Debater", judge="Judge", score=8.5, rationale="rational")
    vote = Vote(debate_id=debate.id, method="plurality", rankings={"order": ["Debater"]})
    db_session.add(score)
    db_session.add(vote)
    
    db_session.commit()

    # Call /retry on "judge" stage
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(
            f"/api/v1/debates/{debate.id}/retry",
            json={"stage_key": "judge"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"
        assert response.json()["retried_stage"] == "judge"
        mock_dispatch.assert_called_once()

        # Check DB updates:
        # Checkpoints for judge should be deleted
        cps = db_session.exec(select(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id == debate.id)).all()
        cp_keys = [c.stage_key for c in cps]
        assert "draft" in cp_keys
        assert "critique" in cp_keys
        assert "judge" not in cp_keys

        # Scores and votes should be deleted
        scores = db_session.exec(select(Score).where(Score.debate_id == debate.id)).all()
        assert len(scores) == 0
        votes = db_session.exec(select(Vote).where(Vote.debate_id == debate.id)).all()
        assert len(votes) == 0

        # Debate status updated to scheduled
        db_session.refresh(debate)
        assert debate.status == "scheduled"


def test_continue_dispatch_failure_safety(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id="test-continue-fail-safety",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()

    headers = {"X-Idempotency-Key": "test-fail-safety-key"}

    # Mock BackgroundTasks.add_task to throw an error
    with patch("starlette.background.BackgroundTasks.add_task", side_effect=Exception("celery queue full")):
        with pytest.raises(Exception, match="celery queue full"):
            authenticated_client.post(
                f"/api/v1/debates/{debate.id}/continue",
                headers=headers
            )
        
    # Verify the database state was rolled back to perspectives_ready
    db_session.refresh(debate)
    assert debate.status == "perspectives_ready"

    # Verify continuation record is marked as failed
    continuation = db_session.exec(
        select(DebateContinuation).where(
            DebateContinuation.debate_id == debate.id,
            DebateContinuation.idempotency_key == "test-fail-safety-key"
        )
    ).first()
    assert continuation is not None
    assert continuation.status == "failed"
    assert continuation.failure_code == "debate.dispatch_failed"
    assert "celery queue full" in continuation.failure_detail_safe


def test_get_debate_continuation(authenticated_client, db_session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id="test-get-continuation-debate",
        user_id=user.id,
        prompt="Test prompt",
        status="perspectives_ready",
    )
    db_session.add(debate)
    db_session.commit()
    
    continuation = DebateContinuation(
        debate_id=debate.id,
        idempotency_key="get-test-key",
        status="requested",
        user_id=user.id
    )
    db_session.add(continuation)
    db_session.commit()
    
    # Try valid request
    response = authenticated_client.get(f"/api/v1/debates/{debate.id}/continuations/{continuation.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["continuation_id"] == str(continuation.id)
    assert data["status"] == "requested"
    assert data["idempotency_key"] == "get-test-key"
    assert data["created"] is False

    # Try non-existent UUID
    response = authenticated_client.get(f"/api/v1/debates/{debate.id}/continuations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    # Try invalid UUID string format
    response = authenticated_client.get(f"/api/v1/debates/{debate.id}/continuations/not-a-uuid")
    assert response.status_code == 404


