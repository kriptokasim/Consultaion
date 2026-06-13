import pytest
from unittest.mock import patch, MagicMock
from models import Debate, User, DebateContinuation, LLMUsageLog
from sqlmodel import select
from datetime import datetime, timezone


@pytest.mark.anyio
async def test_continue_conditional_transition(authenticated_client, db_session):
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
        assert response.status_code == 409
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
        mock_dispatch.assert_called_once()

        # Check DB status is updated to scheduled
        db_session.refresh(debate_paused)
        assert debate_paused.status == "scheduled"

    # 3. Test sending again (now that it is "scheduled") -> should conflict
    with patch("routes.debates.dispatch_debate_run") as mock_dispatch:
        response = authenticated_client.post(f"/api/v1/debates/{debate_paused.id}/continue")
        assert response.status_code == 409
        mock_dispatch.assert_not_called()


@pytest.mark.anyio
async def test_continue_idempotency_key(authenticated_client, db_session):
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
        # Debate status is currently scheduled, so it returns scheduled
        assert response.json()["status"] == "scheduled"
        mock_dispatch.assert_not_called()

    # If it is marked as failed, retry should be allowed
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
        assert response.status_code == 200
        mock_dispatch.assert_called_once()
        
        db_session.refresh(continuation)
        assert continuation.status == "dispatched"


@pytest.mark.anyio
async def test_continue_preflight_budget(authenticated_client, db_session):
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


@pytest.mark.anyio
async def test_continue_preflight_circuit_breaker(authenticated_client, db_session):
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
