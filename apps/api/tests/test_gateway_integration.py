from unittest.mock import patch

import pytest
from agents import UsageCall
from auth import COOKIE_NAME
from fastapi.testclient import TestClient
from llm_errors import TransientLLMError
from model_gateway.agent_bridge import call_model_via_gateway
from model_gateway.types import (
    GatewayModelCallResult,
    GatewayModelRestrictedError,
    GatewayQuotaExceededError,
)
from models import Debate, User
from sqlmodel import Session, select

from tests.utils import settings_context


@pytest.mark.anyio
async def test_gateway_result_mapping_success():
    """Verify call_model_via_gateway maps success result to UsageCall correctly."""
    mock_result = GatewayModelCallResult(
        content="Response content",
        model_used="gpt-4o",
        provider="openai",
        success=True,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.002,
        gateway="model_gateway_v1",
        model_pool="pro_pool",
        routing_policy="pro-direct-pool",
        user_plan="pro",
        estimated_cost_usd=0.0015,
        retry_count=0
    )
    
    with patch("model_gateway.route_llm_call", return_value=mock_result):
        content, call_usage = await call_model_via_gateway(
            messages=[{"role": "user", "content": "test"}],
            model_id="gpt4o-deep",
            role="tester",
            user_plan="pro",
            gateway_policy="direct"
        )
        
        assert content == "Response content"
        assert isinstance(call_usage, UsageCall)
        assert call_usage.model == "gpt-4o"
        assert call_usage.provider == "openai"
        assert call_usage.prompt_tokens == 100.0
        assert call_usage.completion_tokens == 50.0
        assert call_usage.total_tokens == 150.0
        assert call_usage.cost_usd == 0.002
        assert call_usage.gateway == "model_gateway_v1"
        assert call_usage.model_pool == "pro_pool"
        assert call_usage.routing_policy == "pro-direct-pool"
        assert call_usage.user_plan == "pro"
        assert call_usage.estimated_cost_usd == 0.0015
        assert call_usage.retry_count == 0

@pytest.mark.anyio
async def test_gateway_exceptions_wrapped_correctly():
    """Verify that GatewayQuotaExceededError and GatewayModelRestrictedError are mapped to TransientLLMError."""
    with patch("model_gateway.route_llm_call", side_effect=GatewayQuotaExceededError("Quota exceeded cap")):
        with pytest.raises(TransientLLMError) as exc_info:
            await call_model_via_gateway(
                messages=[{"role": "user", "content": "test"}],
                model_id="gpt4o-deep",
                role="tester",
                user_plan="free",
            )
        assert "Quota exceeded cap" in str(exc_info.value)
        assert isinstance(exc_info.value.cause, GatewayQuotaExceededError)

    with patch("model_gateway.route_llm_call", side_effect=GatewayModelRestrictedError("Restricted model tier")):
        with pytest.raises(TransientLLMError) as exc_info:
            await call_model_via_gateway(
                messages=[{"role": "user", "content": "test"}],
                model_id="gpt4o-deep",
                role="tester",
                user_plan="free",
            )
        assert "Restricted model tier" in str(exc_info.value)
        assert isinstance(exc_info.value.cause, GatewayModelRestrictedError)

def test_free_user_credits_enforcement(authenticated_client: TestClient, db_session: Session):
    """Verify free users are checked against their hosted credits limit and blocked when exhausted."""
    # 1. Reset user plan to free and set credits
    user = db_session.exec(select(User)).first()
    assert user is not None
    
    user.plan = "free"
    user.hosted_credits_limit = 5
    user.hosted_credits_used = 4
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Next run should succeed
    res = authenticated_client.post(
        "/debates",
        json={"prompt": "Next run within limits", "mode": "arena"}
    )
    assert res.status_code == 200
    
    # Reload and check credits incremented
    db_session.refresh(user)
    assert user.hosted_credits_used == 5
    
    # Subsequent run should fail as credits are now 5/5 (exhausted)
    res_exhausted = authenticated_client.post(
        "/debates",
        json={"prompt": "Run that exceeds credit limits", "mode": "arena"}
    )
    assert res_exhausted.status_code == 400
    data = res_exhausted.json()
    assert "exhausted" in data["error"]["message"].lower()

def test_pro_user_not_blocked_by_credits(authenticated_client: TestClient, db_session: Session):
    """Verify Pro/Enterprise users are never constrained by free hosted credits."""
    user = db_session.exec(select(User)).first()
    assert user is not None
    
    # Enable owner override for this user so get_active_plan returns Pro plan
    with settings_context(OWNER_EMAIL_ALLOWLIST=user.email, OWNER_PLAN="pro"):
        user.plan = "pro"
        user.hosted_credits_limit = 5
        user.hosted_credits_used = 10  # Exceeds the limit
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Debate creation should bypass limits successfully
        res = authenticated_client.post(
            "/debates",
            json={"prompt": "Pro user should bypass limits", "mode": "arena"}
        )
        assert res.status_code == 200
        
        # Check that credits did NOT increment for pro user
        db_session.refresh(user)
        assert user.hosted_credits_used == 10

@pytest.mark.anyio
async def test_failed_run_refunds_credits(db_session: Session):
    """Verify that a failed debate runner triggers a hosted credit refund for free users."""
    from orchestrator import run_debate
    
    with settings_context(FAST_DEBATE="1"):
        # 1. Setup a unique free user with 1 used credit
        import uuid
        email = f"free_refund_{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash="hash", plan="free", hosted_credits_limit=5, hosted_credits_used=1)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    
        # 2. Setup a dummy debate queued
        debate = Debate(
            id="dummy-failed-debate-id",
            prompt="Test failed refund",
            status="queued",
            config={},
            user_id=user.id,
            model_id="gpt4o-deep",
            mode="arena"
        )
        db_session.add(debate)
        db_session.commit()
        
        # 3. Trigger run_debate, forcing an exception inside the mock run execution
        # to test refund triggering
        with patch("orchestrator._run_mock_debate", side_effect=TransientLLMError("Temporary provider fail")):
            await run_debate(
                debate_id="dummy-failed-debate-id",
                prompt="Test failed refund",
                channel_id="dummy-channel",
                config_data={},
                model_id="gpt4o-deep"
            )
            
        # 4. Verify user was refunded (credits_used went from 1 -> 0)
        db_session.commit()
        db_session.refresh(user)
        assert user.hosted_credits_used == 0



def test_public_dto_safeguard(client: TestClient, authenticated_client: TestClient, db_session: Session):
    """Ensure that the public debate DTO completely filters out internal gateway fields."""
    user = db_session.exec(select(User)).first()
    assert user is not None
    
    # Create a debate
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Safeguard test prompt for security review", "mode": "arena"}
    )
    debate_id = create_res.json()["id"]
    
    # Toggle public using the API
    share_res = authenticated_client.post(
        f"/debates/{debate_id}/share",
        json={"is_public": True}
    )
    assert share_res.status_code == 200
    
    # Update gateway metadata fields on the debate directly in DB
    debate = db_session.get(Debate, debate_id)
    debate.gateway_policy = "fallback"
    debate.routing_policy = "fallback-pool"
    db_session.add(debate)
    db_session.commit()
    db_session.refresh(debate)
    
    # Fetch debate publicly (unauthenticated client)
    # Using client (which is unauthenticated) instead of authenticated_client
    client.cookies.delete(COOKIE_NAME)
    get_res = client.get(f"/debates/{debate_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    
    # Verify sensitive gateway/plan metadata is absent
    assert "gateway_policy" not in data
    assert "routing_policy" not in data
    assert "model_pool" not in data
    assert "routing_meta" not in data
    assert "user_plan" not in data


@pytest.mark.anyio
async def test_used_equals_limit_gateway_block(db_session: Session):
    """Verify that when user's hosted_credits_used equals hosted_credits_limit, has_credits is False and pro pool is restricted."""
    # 1. Setup a unique free user with used == limit (e.g. 5 == 5)
    import uuid

    from model_gateway import route_llm_call
    from model_gateway.types import GatewayModelRestrictedError, GatewayRequest
    email = f"free_limit_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=email, password_hash="hash", plan="free", hosted_credits_limit=5, hosted_credits_used=5)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # 2. Try to call a restricted Pro model (e.g., claude-3-5-sonnet) with this user ID
    # Since has_credits is False, it should raise GatewayModelRestrictedError because the free user
    # does not have active credits to bypass the plan restrictions.
    req = GatewayRequest(
        messages=[{"role": "user", "content": "hello"}],
        model_id="claude-3-5-sonnet",
        role="tester",
        user_id=user.id,
        user_plan="free"
    )
    
    with pytest.raises(GatewayModelRestrictedError) as exc_info:
        await route_llm_call(req, db_session=db_session)
    assert "restricted" in str(exc_info.value).lower()

