"""Contract tests for the LiteLLM proxy transport seam.

Two properties matter more than any individual behaviour here:

1. With MODEL_GATEWAY_BACKEND unset or "direct", the seam is completely inert.
   That is the rollback guarantee, and it is the difference between a reversible
   migration and a one-way door.
2. When the proxy backend is half-configured, the app fails loudly at boot
   rather than quietly at the first user debate.
"""
from __future__ import annotations

import pytest

from model_gateway import proxy_transport
from model_gateway.proxy_transport import (
    ProxyConfigurationError,
    proxy_enabled,
    proxy_overrides,
    resolve_deployment,
    validate_proxy_configuration,
)


@pytest.fixture
def proxy_on(monkeypatch):
    monkeypatch.setattr("config.settings.MODEL_GATEWAY_BACKEND", "proxy")
    monkeypatch.setattr("config.settings.LITELLM_PROXY_URL", "http://litellm:4000")
    monkeypatch.setattr("config.settings.LITELLM_PROXY_API_KEY", "sk-virtual-test")


# --- Inertness on the direct path -------------------------------------------

def test_direct_backend_produces_no_overrides(monkeypatch):
    monkeypatch.setattr("config.settings.MODEL_GATEWAY_BACKEND", "direct")
    assert proxy_enabled() is False
    assert proxy_overrides("openai_fast", "openai/gpt-4o-mini") == {}


def test_unset_backend_defaults_to_direct(monkeypatch):
    monkeypatch.delattr("config.settings.MODEL_GATEWAY_BACKEND", raising=False)
    assert proxy_overrides("openai_fast", "openai/gpt-4o-mini") == {}


def test_proxy_backend_without_url_falls_back_to_direct(monkeypatch):
    """A missing URL must not take the product down.

    Failing open here is deliberate: validate_proxy_configuration() is what makes
    the misconfiguration loud at boot, so a request arriving in this state should
    still be answerable rather than dropped.
    """
    monkeypatch.setattr("config.settings.MODEL_GATEWAY_BACKEND", "proxy")
    monkeypatch.setattr("config.settings.LITELLM_PROXY_URL", None)
    assert proxy_enabled() is False
    assert proxy_overrides("openai_fast", "openai/gpt-4o-mini") == {}


# --- Behaviour with the proxy on --------------------------------------------

def test_overrides_redirect_to_proxy(proxy_on):
    overrides = proxy_overrides("openai_fast", "openai/gpt-4o-mini")
    assert overrides["api_base"] == "http://litellm:4000"
    assert overrides["api_key"] == "sk-virtual-test"
    assert overrides["custom_llm_provider"] == "openai"
    assert overrides["model"] == "openai/seat_openai_fast"


def test_trailing_slash_is_normalised(proxy_on, monkeypatch):
    monkeypatch.setattr("config.settings.LITELLM_PROXY_URL", "http://litellm:4000/")
    assert proxy_overrides("openai_fast", "x")["api_base"] == "http://litellm:4000"


def test_byok_api_key_bypasses_the_proxy(proxy_on):
    """A caller-supplied key means the user is billing their own account.

    Routing that call through the platform's virtual key would bill us for usage
    the user is already paying for, and would count their spend against our
    global ceiling.
    """
    assert proxy_overrides("openai_fast", "openai/gpt-4o-mini", api_key="sk-user-own") == {}


def test_unknown_model_passes_the_resolved_slug_through(proxy_on):
    overrides = proxy_overrides("some-unmapped-model", "openrouter/vendor/model")
    assert overrides["model"] == "openrouter/vendor/model"


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("anthropic_reasoning", "openai/seat_anthropic"),
        ("groq_fast", "openai/seat_groq"),
        ("router-deep", "openai/seat_free_glm"),
        ("openrouter-nemotron-free", "openai/seat_free_nemotron"),
    ],
)
def test_known_seats_map_to_named_deployments(proxy_on, model_id, expected):
    assert resolve_deployment(model_id, "fallback") == expected


def test_free_arena_seats_map_to_distinct_deployments(proxy_on):
    """The free roster must stay four different upstreams.

    Collapsing these onto one deployment would make a free debate four copies of
    the same model agreeing with itself.
    """
    from parliament.model_registry import FREE_ARENA_MODELS

    deployments = [resolve_deployment(m, m) for m in FREE_ARENA_MODELS]
    assert len(set(deployments)) == len(FREE_ARENA_MODELS)


# --- Startup validation ------------------------------------------------------

def test_validation_passes_on_direct(monkeypatch):
    monkeypatch.setattr("config.settings.MODEL_GATEWAY_BACKEND", "direct")
    validate_proxy_configuration()


def test_validation_passes_when_fully_configured(proxy_on):
    validate_proxy_configuration()


def test_validation_rejects_unknown_backend(monkeypatch):
    monkeypatch.setattr("config.settings.MODEL_GATEWAY_BACKEND", "sidecar")
    with pytest.raises(ProxyConfigurationError):
        validate_proxy_configuration()


@pytest.mark.parametrize("missing", ["LITELLM_PROXY_URL", "LITELLM_PROXY_API_KEY"])
def test_validation_fails_closed_when_half_configured(proxy_on, monkeypatch, missing):
    monkeypatch.setattr(f"config.settings.{missing}", None)
    with pytest.raises(ProxyConfigurationError) as exc:
        validate_proxy_configuration()
    assert missing in str(exc.value)


# --- Kill switch -------------------------------------------------------------

@pytest.mark.anyio
async def test_kill_switch_refuses_dispatch_before_any_spend(monkeypatch):
    from debate_dispatch import LLMKillSwitchEngaged, dispatch_debate_run

    monkeypatch.setattr("config.settings.LLM_KILL_SWITCH_ENABLED", True)

    with pytest.raises(LLMKillSwitchEngaged):
        await dispatch_debate_run(
            debate_id="d1",
            prompt="test",
            channel_id="c1",
            config_data={},
            model_id="router-smart",
        )


@pytest.mark.anyio
async def test_kill_switch_off_does_not_block(monkeypatch):
    """Guard against the switch defaulting on and silently pausing the product."""
    from config import settings

    assert getattr(settings, "LLM_KILL_SWITCH_ENABLED", False) is False


def test_proxy_deployment_table_covers_every_static_arena_seat():
    """Every seat the arena can serve must have a proxy deployment.

    A seat missing from the table still works (it falls through to the wildcard
    deployment), but it silently loses its per-deployment cooldown and fallback
    chain -- which is the reason for running the proxy at all.
    """
    from parliament.model_registry import FREE_ARENA_MODELS

    for model_id in FREE_ARENA_MODELS:
        assert model_id in proxy_transport.PROXY_DEPLOYMENT_NAMES, (
            f"free arena seat {model_id!r} has no proxy deployment"
        )
