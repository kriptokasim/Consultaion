from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents import NON_RETRYABLE_LLM_ERROR_CODES
from model_gateway.adapters import _has_hidden_reasoning_activity
from model_gateway.provider_health import record_failure, record_success


def test_reasoning_activity_is_detected_without_exposing_content() -> None:
    delta = SimpleNamespace(content=None, reasoning_content="private reasoning")

    assert _has_hidden_reasoning_activity(delta) is True
    assert getattr(delta, "content", None) is None


def test_empty_delta_is_not_reasoning_activity() -> None:
    delta = SimpleNamespace(content=None, reasoning_content=None, thinking=None)

    assert _has_hidden_reasoning_activity(delta) is False


def test_deterministic_gateway_errors_are_not_retryable() -> None:
    assert {
        "invalid_credentials",
        "insufficient_balance",
        "model_key_unresolved",
        "unknown_model",
    }.issubset(NON_RETRYABLE_LLM_ERROR_CODES)


def test_transient_gateway_errors_remain_retryable() -> None:
    assert "rate_limit_exceeded" not in NON_RETRYABLE_LLM_ERROR_CODES
    assert "model_timeout" not in NON_RETRYABLE_LLM_ERROR_CODES


def test_user_byok_health_events_do_not_touch_shared_redis_state() -> None:
    with patch("model_gateway.provider_health.get_redis") as get_redis:
        redis = MagicMock()
        get_redis.return_value = redis

        record_failure(
            "openai",
            "invalid_credentials",
            "invalid user key",
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
