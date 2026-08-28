from unittest.mock import AsyncMock, patch

import pytest
from model_gateway import route_llm_call, route_llm_stream
from model_gateway.adapters import DirectProviderAdapter, OpenRouterAdapter
from model_gateway.costs import check_credit_and_cost_safety
from model_gateway.policy import determine_routing_strategy
from model_gateway.pools import get_model_pool, validate_user_access_to_model
from model_gateway.types import (
    GatewayModelCallResult,
    GatewayModelRestrictedError,
    GatewayQuotaExceededError,
    GatewayRequest,
)
from parliament.model_registry import get_arena_models


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

@pytest.mark.anyio
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

@pytest.mark.anyio
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

@pytest.mark.anyio
async def test_route_llm_call_fallback_loop(monkeypatch):
    req = GatewayRequest(
        messages=[{"role": "user", "content": "hello"}],
        model_id="gpt4o-deep",
        role="user",
        gateway_policy="fallback",
        user_plan="pro",
    )
    monkeypatch.setattr("config.settings.OPENROUTER_API_KEY", "test-openrouter-key")

    fallback_result = GatewayModelCallResult(
        content="fallback answer",
        model_used="openrouter/openai/gpt-4o",
        provider="openrouter",
        success=True,
        model_pool="fallback_pool",
        routing_policy="test-policy-fallback",
    )

    with (
        patch(
            "model_gateway.determine_routing_strategy",
            return_value=(DirectProviderAdapter, "test-policy"),
        ),
        patch(
            "model_gateway.provider_health.is_circuit_open",
            return_value=False,
        ),
        patch.object(
            DirectProviderAdapter,
            "call_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Direct provider down"),
        ),
        patch.object(
            OpenRouterAdapter,
            "call_llm",
            new_callable=AsyncMock,
            return_value=fallback_result,
        ) as mock_fallback,
    ):
        result = await route_llm_call(req)

    assert result.success is True
    mock_fallback.assert_awaited_once()
    fallback_kwargs = mock_fallback.await_args.kwargs
    assert fallback_kwargs["model_id"] == "openai_premium"
    assert fallback_kwargs["api_key"] == "test-openrouter-key"


def test_openrouter_key_enables_full_arena_manifest(monkeypatch):
    monkeypatch.setattr("config.settings.USE_MOCK", False)
    monkeypatch.setattr("config.settings.OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr("config.settings.OPENAI_API_KEY", None)
    monkeypatch.setattr("config.settings.ANTHROPIC_API_KEY", None)
    monkeypatch.setattr("config.settings.GEMINI_API_KEY", None)
    monkeypatch.setattr("config.settings.GOOGLE_API_KEY", None)

    assert [model.id for model in get_arena_models()] == [
        "gpt4o-deep",
        "claude-sonnet",
        "gemini-2-5-pro",
        "deepseek-r1",
    ]


@pytest.mark.anyio
async def test_stream_uses_openrouter_when_direct_key_is_missing(monkeypatch):
    monkeypatch.setattr("config.settings.OPENAI_API_KEY", None)
    monkeypatch.setattr("config.settings.OPENROUTER_API_KEY", "test-openrouter-key")

    fallback_result = GatewayModelCallResult(
        content="routed answer",
        model_used="openrouter/openai/gpt-4o",
        provider="openrouter",
        success=True,
        model_pool="fallback_pool",
        routing_policy="stream-openrouter-fallback",
    )

    async def on_delta(_delta):
        return None

    with (
        patch(
            "model_gateway.provider_health.is_circuit_open",
            return_value=False,
        ),
        patch.object(
            DirectProviderAdapter,
            "stream_llm",
            new_callable=AsyncMock,
        ) as direct_stream,
        patch.object(
            OpenRouterAdapter,
            "stream_llm",
            new_callable=AsyncMock,
            return_value=fallback_result,
        ) as router_stream,
    ):
        result = await route_llm_stream(
            messages=[{"role": "user", "content": "hello"}],
            model_id="gpt4o-deep",
            on_delta=on_delta,
        )

    direct_stream.assert_not_awaited()
    router_stream.assert_awaited_once()
    fallback_kwargs = router_stream.await_args.kwargs
    assert fallback_kwargs["model_id"] == "openai_premium"
    assert fallback_kwargs["api_key"] == "test-openrouter-key"
    assert result.success is True
    assert result.fallback_used is True
    assert result.retry_count == 1
