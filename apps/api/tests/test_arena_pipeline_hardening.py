from unittest.mock import MagicMock, patch

import pytest
from model_gateway.model_target import UnknownModelError, resolve_model_target
from model_gateway.provider_health import (
    CIRCUIT_FAILURE_THRESHOLD,
    is_circuit_open,
    record_failure,
)

from config import settings


@pytest.mark.asyncio
async def test_canonical_model_resolution_via_alias():
    """gpt-4o is an alias for canonical key openai_premium."""
    t1 = resolve_model_target("gpt-4o")
    assert t1.canonical_id == "openai_premium"
    assert t1.provider == "openai"
    assert t1.litellm_model == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_canonical_model_resolution_via_litellm_string():
    """openai/gpt-4o is a litellm string alias for openai_premium."""
    t2 = resolve_model_target("openai/gpt-4o")
    assert t2.canonical_id == "openai_premium"
    assert t2.provider == "openai"


@pytest.mark.asyncio
async def test_canonical_model_resolution_via_anthropic_alias():
    """claude-sonnet is an alias for anthropic_reasoning."""
    t3 = resolve_model_target("claude-sonnet")
    assert t3.canonical_id == "anthropic_reasoning"
    assert t3.provider == "anthropic"


@pytest.mark.asyncio
async def test_canonical_model_resolution_unknown_raises():
    """Completely unknown model raises UnknownModelError."""
    with pytest.raises(UnknownModelError):
        resolve_model_target("nonexistent-model-xyz-999")


@pytest.mark.asyncio
async def test_model_granular_health_tracking():
    """Model-granular circuit breaker trips independently per model."""
    provider = "test_provider_isolated"
    model_a = "model_a_test"
    model_b = "model_b_test"

    with patch("model_gateway.provider_health.get_redis") as mock_get_redis:
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        state_store = {}

        def mock_get(key):
            return state_store.get(key)

        def mock_set(key, val, ex=None):
            state_store[key] = val

        def mock_incr(key):
            state_store[key] = state_store.get(key, 0) + 1
            return state_store[key]

        def mock_expire(key, ttl):
            pass  # no-op for test

        mock_redis.get.side_effect = mock_get
        mock_redis.set.side_effect = mock_set
        mock_redis.incr.side_effect = mock_incr
        mock_redis.expire.side_effect = mock_expire

        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = None
        mock_redis.pipeline.return_value = mock_pipeline

        # Verify both models start healthy
        assert not is_circuit_open(provider, canonical_model_id=model_a)
        assert not is_circuit_open(provider, canonical_model_id=model_b)

        # Trip model_a circuit breaker with enough failures
        for _ in range(CIRCUIT_FAILURE_THRESHOLD + 1):
            record_failure(provider, "500", "Internal Error", canonical_model_id=model_a)

        # Model A circuit breaker should be open
        assert is_circuit_open(provider, canonical_model_id=model_a)
        # Model B should remain healthy
        assert not is_circuit_open(provider, canonical_model_id=model_b)


@pytest.mark.asyncio
async def test_staged_streaming_config_defaults():
    """Verify the new staged timeout config defaults are present."""
    assert settings.ARENA_FIRST_TOKEN_TIMEOUT_MS == 15000
    assert settings.ARENA_ACTIVE_STREAM_TIMEOUT_MS == 30000
    assert settings.ARENA_STREAM_TOTAL_TIMEOUT_MS == 60000
    assert settings.MIN_SUCCESSFUL_RESPONSES_FOR_SYNTHESIS == 2
    assert settings.ARENA_FAST_FINALIZATION_ENABLED is True
    assert settings.ARENA_FINAL_CONVERGENCE_GRACE_MS == 8000


def test_user_scoped_failures_do_not_mutate_shared_circuit():
    from model_gateway.provider_health import record_failure, record_success

    with patch("model_gateway.provider_health.get_redis") as mock_get_redis:
        redis = MagicMock()
        mock_get_redis.return_value = redis

        record_failure(
            "openai",
            "invalid_credentials",
            "bad user key",
            canonical_model_id="openai_fast",
            credential_scope="user",
        )
        record_success(
            "openai",
            canonical_model_id="openai_fast",
            credential_scope="user",
        )

        redis.set.assert_not_called()
        redis.incr.assert_not_called()
        redis.pipeline.assert_not_called()


def test_server_scoped_invalid_credentials_still_trip_global_circuit():
    from model_gateway.provider_health import get_global_status_key, record_failure

    with patch("model_gateway.provider_health.get_redis") as mock_get_redis:
        redis = MagicMock()
        mock_get_redis.return_value = redis

        record_failure(
            "openai",
            "invalid_credentials",
            "bad hosted key",
            canonical_model_id="openai_fast",
            credential_scope="server",
        )

        redis.set.assert_called_once_with(
            get_global_status_key("openai"),
            "open",
            ex=3600,
        )
