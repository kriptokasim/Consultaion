"""The status page must not report a dead provider as operational.

/api/status used to decide a provider was "operational" from
`bool(settings.OPENAI_API_KEY)` -- whether an environment variable was a
non-empty string. It never called the provider, never checked credit, never read
the circuit breaker.

So on 2026-09-07, with OpenAI returning credit_balance_exhausted, Anthropic
insufficient_balance and Gemini invalid_credentials -- two of them tripping the
global circuit -- the public status page showed "All Systems Operational". An
invalid key is still a non-empty string.

get_provider_circuit_status() already existed in the same module and simply was
not called from here.
"""
from __future__ import annotations

import pytest

from routes import ops

pytestmark = pytest.mark.timeout(10)


@pytest.fixture
def circuit(monkeypatch):
    state = {}

    def fake(provider: str):
        return state.get(provider, {
            "state": "closed", "consecutive_failures": 0,
            "ttl": None, "redis_connected": True,
        })

    monkeypatch.setattr(ops, "get_provider_circuit_status", fake)
    return state


def test_an_unconfigured_provider_is_not_configured(circuit):
    assert ops._provider_status("openai", False)["status"] == "not_configured"


def test_a_healthy_provider_is_operational(circuit):
    entry = ops._provider_status("openai", True)
    assert entry["status"] == "operational"
    assert entry["configured"] is True


def test_a_tripped_circuit_is_an_outage_not_operational(circuit):
    """The exact production case: key present, provider unusable."""
    circuit["anthropic"] = {
        "state": "open", "consecutive_failures": 5,
        "ttl": 3600, "redis_connected": True,
    }
    entry = ops._provider_status("anthropic", True)

    assert entry["status"] == "outage", "a key string is not evidence of health"
    assert entry["consecutive_failures"] == 5
    assert entry["retry_in_seconds"] == 3600


def test_failures_short_of_tripping_show_as_degraded(circuit):
    """The window a status page is actually worth having."""
    circuit["gemini"] = {
        "state": "closed", "consecutive_failures": 2,
        "ttl": None, "redis_connected": True,
    }
    assert ops._provider_status("gemini", True)["status"] == "degraded"


def test_an_unreadable_breaker_is_labelled_unverified(circuit):
    """"closed by default" must not masquerade as a passing health check."""
    circuit["openai"] = {
        "state": "closed", "consecutive_failures": 0,
        "ttl": None, "redis_connected": False,
    }
    entry = ops._provider_status("openai", True)
    assert entry["health_source"] == "unverified"


@pytest.mark.anyio
async def test_overall_status_degrades_when_a_provider_is_out(circuit, monkeypatch):
    async def db_ok():
        return True, ""

    async def sse_ok():
        return True, ""

    monkeypatch.setattr(ops, "_db_readiness_async", db_ok)
    monkeypatch.setattr(ops, "check_sse_readiness", sse_ok)
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setattr(f"config.settings.{name}", "sk-present", raising=False)
    monkeypatch.setattr("config.settings.GOOGLE_API_KEY", None, raising=False)
    monkeypatch.setattr("config.settings.FREE_ONLY_MODE", False, raising=False)

    circuit["anthropic"] = {
        "state": "open", "consecutive_failures": 4, "ttl": 900, "redis_connected": True,
    }

    payload = await ops.api_status()

    assert payload["status"] == "degraded", (
        "one provider in outage must not leave the site reporting operational"
    )
    assert payload["providers"]["anthropic"]["status"] == "outage"
    assert payload["providers"]["openai"]["status"] == "operational"


@pytest.mark.anyio
async def test_every_provider_out_is_a_major_outage(circuit, monkeypatch):
    """Nothing left to serve a debate with is not merely 'degraded'."""
    async def db_ok():
        return True, ""

    async def sse_ok():
        return True, ""

    monkeypatch.setattr(ops, "_db_readiness_async", db_ok)
    monkeypatch.setattr(ops, "check_sse_readiness", sse_ok)
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setattr(f"config.settings.{name}", "sk-present", raising=False)
    monkeypatch.setattr("config.settings.GOOGLE_API_KEY", None, raising=False)

    for name in ("openai", "anthropic", "gemini", "openrouter"):
        circuit[name] = {
            "state": "open", "consecutive_failures": 9, "ttl": 3600, "redis_connected": True,
        }

    payload = await ops.api_status()
    assert payload["status"] == "major_outage"


@pytest.mark.anyio
async def test_free_only_mode_is_disclosed(circuit, monkeypatch):
    """SOTA keys can be healthy while no SOTA model is serving anything."""
    async def db_ok():
        return True, ""

    async def sse_ok():
        return True, ""

    monkeypatch.setattr(ops, "_db_readiness_async", db_ok)
    monkeypatch.setattr(ops, "check_sse_readiness", sse_ok)
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setattr(f"config.settings.{name}", "sk-present", raising=False)
    monkeypatch.setattr("config.settings.GOOGLE_API_KEY", None, raising=False)
    monkeypatch.setattr("config.settings.FREE_ONLY_MODE", True, raising=False)

    payload = await ops.api_status()
    assert payload.get("free_only_mode") is True
