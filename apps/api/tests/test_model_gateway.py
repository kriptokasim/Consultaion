import pytest
from unittest.mock import AsyncMock, patch
from model_gateway.types import GatewayRequest, GatewayModelRestrictedError, GatewayQuotaExceededError
from model_gateway.pools import get_model_pool, validate_user_access_to_model
from model_gateway.costs import check_credit_and_cost_safety
from model_gateway.policy import determine_routing_strategy
from model_gateway import route_llm_call
from model_gateway.adapters import MockAdapter, DirectProviderAdapter, OpenRouterAdapter

def test_model_pool_lookup():
    assert get_model_pool("mimo-v2-free") == "free_hosted_pool"
    assert get_model_pool("gpt4o-deep") == "premium_pool"
    # Unknown model should default to premium_pool
    assert get_model_pool("unknown-model") == "premium_pool"

def test_validate_user_access():
    # Free user calling free model -> ok
    validate_user_access_to_model("mimo-v2-free", "free")
    # Pro user calling pro model -> ok
    validate_user_access_to_model("gpt4o-deep", "pro")
    
    # Free user calling pro model -> restricted error
    with pytest.raises(GatewayModelRestrictedError):
        validate_user_access_to_model("gpt4o-deep", "free")

@pytest.mark.asyncio
async def test_credit_and_cost_safety():
    # Inside cap -> ok
    await check_credit_and_cost_safety(user_id="test-user", user_plan="free", estimated_cost_usd=0.01)
    
    # Exceeding single run cap -> quota exceeded error
    with pytest.raises(GatewayQuotaExceededError):
        await check_credit_and_cost_safety(user_id="test-user", user_plan="free", estimated_cost_usd=1.0)

def test_determine_routing_strategy():
    # Auto policy with free plan -> OpenRouterAdapter
    req_free = GatewayRequest(
        messages=[{"role": "user", "content": "hello"}],
        model_id="mimo-v2-free",
        role="user",
        gateway_policy="auto",
        user_plan="free"
    )
    adapter_cls, policy = determine_routing_strategy(req_free, force_real=True)
    assert adapter_cls == DirectProviderAdapter
    assert policy == "free-direct-pool"

    # Auto policy with pro plan -> DirectProviderAdapter
    req_pro = GatewayRequest(
        messages=[{"role": "user", "content": "hello"}],
        model_id="gpt4o-deep",
        role="user",
        gateway_policy="auto",
        user_plan="pro"
    )
    adapter_cls, policy = determine_routing_strategy(req_pro, force_real=True)
    assert adapter_cls == DirectProviderAdapter
    assert policy == "direct-smart-pro"

@pytest.mark.asyncio
async def test_route_llm_call_success():
    req = GatewayRequest(
        messages=[{"role": "user", "content": "hello"}],
        model_id="mimo-v2-free",
        role="user",
        gateway_policy="auto",
        user_plan="free"
    )
    # Under test environment determine_routing_strategy falls back to MockAdapter
    res = await route_llm_call(req)
    assert res.success is True
    assert "[Mock response from mimo-v2-free]" in res.content
    assert res.model_pool == "free_hosted_pool"

@pytest.mark.asyncio
async def test_route_llm_call_fallback_loop():
    req = GatewayRequest(
        messages=[{"role": "user", "content": "hello"}],
        model_id="gpt4o-deep",
        role="user",
        gateway_policy="fallback",
        user_plan="pro"
    )
    
    # We patch determine_routing_strategy to force DirectProviderAdapter as primary,
    # and mock its call_llm to raise an error. The routing coordinator should catch
    # the failure and fall back to OpenRouterAdapter.
    with patch("model_gateway.determine_routing_strategy") as mock_strategy:
        mock_strategy.return_value = (DirectProviderAdapter, "test-policy")
        
        with patch.object(DirectProviderAdapter, "call_llm", side_effect=RuntimeError("Direct Provider Down")):
            with patch.object(OpenRouterAdapter, "call_llm") as mock_fallback:
                mock_fallback.return_value = AsyncMock()
                # Run the route call
                await route_llm_call(req)
                
                # Check that fallback was called
                mock_fallback.assert_called_once()
