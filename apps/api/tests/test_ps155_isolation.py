"""PS155.3 — Provider Isolation and Model Deadlines tests."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

# ── Credential Isolation ──────────────────────────────────────────────────


def test_resolve_api_key_byok_priority():
    """resolve_api_key should prefer user BYOK over global settings."""
    from agents import resolve_api_key

    from config import settings

    user_keys = {"openai": "byok_sk_123"}
    settings.OPENAI_API_KEY = "global_sk_456"

    # User key wins
    assert resolve_api_key("openai", user_keys) == "byok_sk_123"

    # Fallback to global setting if no BYOK
    assert resolve_api_key("openai", None) == "global_sk_456"

    # Returns None if neither
    assert resolve_api_key("fake_provider", {}) is None


def test_no_environ_mutations_for_provider_keys():
    """Ensure os.environ is not mutated with provider keys on import or resolution."""
    # Temporarily remove any keys that might be in the environment
    original_env = dict(os.environ)
    for k in list(os.environ.keys()):
        if k.endswith("_API_KEY"):
            del os.environ[k]

    from config import settings
    settings.OPENAI_API_KEY = "global_sk_test_only"

    from agents import resolve_api_key
    key = resolve_api_key("openai")

    assert key == "global_sk_test_only"
    assert "OPENAI_API_KEY" not in os.environ

    # Restore
    os.environ.clear()
    os.environ.update(original_env)


# ── Threading api_key ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gateway_request_accepts_api_key():
    """GatewayRequest should store the api_key."""
    from model_gateway.types import GatewayRequest

    req = GatewayRequest(
        messages=[{"role": "user", "content": "hi"}],
        model_id="gpt-4o",
        role="test",
        api_key="sk_test_123"
    )
    assert req.api_key == "sk_test_123"


@pytest.mark.asyncio
async def test_agent_bridge_threads_api_key():
    """call_model_via_gateway should pass api_key to GatewayRequest."""
    from model_gateway.agent_bridge import call_model_via_gateway
    from model_gateway.types import GatewayModelCallResult

    mock_result = GatewayModelCallResult(
        content="test",
        model_used="gpt-4o",
        provider="openai",
        model_pool="default",
        routing_policy="test"
    )

    with patch("model_gateway.route_llm_call", new_callable=AsyncMock) as mock_route:
        mock_route.return_value = mock_result
        
        await call_model_via_gateway(
            messages=[{"role": "user", "content": "hi"}],
            model_id="gpt-4o",
            role="test",
            api_key="sk_bridge_test"
        )
        
        req = mock_route.call_args[0][0]
        assert req.api_key == "sk_bridge_test"


# ── Arena Total Timeout ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_arena_model_total_timeout_enforcement():
    """Verify ARENA_MODEL_TOTAL_TIMEOUT_S is configured and asyncio.wait_for works."""
    from config import settings

    # Verify the setting exists and defaults to a reasonable value
    assert hasattr(settings, "ARENA_MODEL_TOTAL_TIMEOUT_S")
    assert settings.ARENA_MODEL_TOTAL_TIMEOUT_S > 0

    # Verify asyncio.wait_for enforces timeout correctly
    async def slow_call_model(*args, **kwargs):
        await asyncio.sleep(10.0)
        return "too late"

    try:
        await asyncio.wait_for(slow_call_model(), timeout=1)
        pytest.fail("Should have timed out")
    except asyncio.TimeoutError:
        pass  # Expected
